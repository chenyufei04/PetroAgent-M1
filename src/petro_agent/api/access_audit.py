"""提供透明的访问 IP 审计与轻量级 API 限流。"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import ipaddress
import logging
import math
import os
from pathlib import Path
from time import monotonic

from starlette.requests import Request

from .request_logging import RecordCountingRotatingFileHandler


IP_AUDIT_LOGGER_NAME = "petro_agent.security.ip_audit"


def _env_bool(name: str, default: bool) -> bool:
    """读取常见布尔环境变量写法，无法识别时采用安全默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_client_ip(request: Request, trust_cloudflare: bool = True) -> str:
    """解析访问 IP；仅信任 Cloudflare 专用头，不采信可随意伪造的通用 XFF。"""
    if trust_cloudflare:
        candidate = request.headers.get("cf-connecting-ip", "").strip()
        try:
            if candidate:
                return str(ipaddress.ip_address(candidate))
        except ValueError:
            # 非法代理头不能进入审计日志，回退到 ASGI 实际连接地址。
            pass
    observed = request.client.host if request.client else "unknown"
    try:
        return str(ipaddress.ip_address(observed))
    except ValueError:
        return "unknown"


def is_page_entry_request(request: Request) -> bool:
    """仅把 GET 首页视为一次页面进入；API、资源加载和内部操作均排除。"""
    return request.method == "GET" and request.url.path == "/"


@dataclass(frozen=True)
class RateLimitDecision:
    """描述一次请求是否通过以及客户端需要等待的秒数。"""

    allowed: bool
    retry_after: int = 0


class AccessAudit:
    """记录进入首页的纯 IP 行，并在内存中限制单个 IP 的 API 请求频率。"""

    def __init__(
        self,
        logger: logging.Logger,
        *,
        enabled: bool = True,
        rate_limit_enabled: bool = True,
        max_requests: int = 120,
        window_seconds: int = 60,
        max_tracked_ips: int = 10_000,
    ) -> None:
        self.logger = logger
        self.enabled = enabled
        self.rate_limit_enabled = rate_limit_enabled
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(1, window_seconds)
        self.max_tracked_ips = max(100, max_tracked_ips)
        # OrderedDict 兼作简单 LRU，防止大量随机来源地址无限占用后端内存。
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()

    def record(self, client_ip: str) -> None:
        """按用户要求只写 IP；时间、路径和请求内容均不进入该文件。"""
        if self.enabled:
            self.logger.info(client_ip)

    def check_rate_limit(self, client_ip: str, now: float | None = None) -> RateLimitDecision:
        """采用滑动时间窗限制 API 频率；静态资源由调用方排除。"""
        if not self.rate_limit_enabled:
            return RateLimitDecision(True)

        current = monotonic() if now is None else now
        cutoff = current - self.window_seconds
        bucket = self._requests.get(client_ip)
        if bucket is None:
            if len(self._requests) >= self.max_tracked_ips:
                self._requests.popitem(last=False)
            bucket = deque()
            self._requests[client_ip] = bucket
        else:
            self._requests.move_to_end(client_ip)

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            retry_after = max(1, math.ceil(self.window_seconds - (current - bucket[0])))
            return RateLimitDecision(False, retry_after)
        bucket.append(current)
        return RateLimitDecision(True)


def configure_access_audit(
    project_root: Path,
    *,
    log_dir: Path | None = None,
    max_records: int | None = None,
) -> AccessAudit:
    """根据环境变量配置独立 IP 日志、日志轮转和 API 访问频率限制。"""
    logger = logging.getLogger(IP_AUDIT_LOGGER_NAME)
    if not any(getattr(handler, "_petro_agent_ip_audit_handler", False) for handler in logger.handlers):
        configured_dir = log_dir or Path(os.getenv("PETRO_AGENT_LOG_DIR", "outputs/logs"))
        if not configured_dir.is_absolute():
            configured_dir = project_root / configured_dir
        configured_dir.mkdir(parents=True, exist_ok=True)

        file_name = Path(os.getenv("PETRO_AGENT_IP_AUDIT_LOG_FILE", "access_ip.log")).name
        max_bytes = max(1024, int(os.getenv("PETRO_AGENT_IP_AUDIT_MAX_BYTES", "1048576")))
        backup_count = max(1, int(os.getenv("PETRO_AGENT_IP_AUDIT_BACKUP_COUNT", "10")))
        record_limit = max_records or max(
            1, int(os.getenv("PETRO_AGENT_IP_AUDIT_MAX_RECORDS", "1000"))
        )
        handler = RecordCountingRotatingFileHandler(
            configured_dir / file_name,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            max_records=record_limit,
        )
        # 该专用文件严格保持一行一个 IP，不附加时间、路径或其他个人信息。
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._petro_agent_ip_audit_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return AccessAudit(
        logger,
        enabled=_env_bool("PETRO_AGENT_IP_AUDIT_ENABLED", True),
        rate_limit_enabled=_env_bool("PETRO_AGENT_RATE_LIMIT_ENABLED", True),
        max_requests=int(os.getenv("PETRO_AGENT_RATE_LIMIT_MAX_REQUESTS", "120")),
        window_seconds=int(os.getenv("PETRO_AGENT_RATE_LIMIT_WINDOW_SECONDS", "60")),
        max_tracked_ips=int(os.getenv("PETRO_AGENT_RATE_LIMIT_MAX_TRACKED_IPS", "10000")),
    )
