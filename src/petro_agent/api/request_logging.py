"""为 FastAPI 请求提供结构化、可轮转的本地文件日志。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import Any


LOGGER_NAME = "petro_agent.api.access"


class RecordCountingRotatingFileHandler(RotatingFileHandler):
    """同时按日志条数和文件大小轮转，保证单个文件不会无限增长。"""

    def __init__(self, *args, max_records: int = 1000, **kwargs) -> None:
        self.max_records = max(1, max_records)
        super().__init__(*args, **kwargs)
        # 服务重启后从当前文件已有行数继续计数，而不是重新从零开始。
        try:
            with Path(self.baseFilename).open("r", encoding=self.encoding or "utf-8") as handle:
                self.record_count = sum(1 for _ in handle)
        except FileNotFoundError:
            self.record_count = 0

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        return self.record_count >= self.max_records or super().shouldRollover(record)

    def doRollover(self) -> None:
        super().doRollover()
        self.record_count = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.shouldRollover(record):
                self.doRollover()
            logging.FileHandler.emit(self, record)
            self.record_count += 1
        except Exception:
            self.handleError(record)


class JsonLineFormatter(logging.Formatter):
    """把一次接口调用写成单行 JSON，便于人工排查和后续程序分析。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": getattr(record, "event", "api_request"),
            "message": record.getMessage(),
        }
        for field in (
            "request_id", "method", "path", "status_code", "duration_ms",
            "client_ip", "user_agent", "error_type", "error_message",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_api_logger(
    project_root: Path,
    log_dir: Path | None = None,
    max_records: int | None = None,
) -> logging.Logger:
    """按环境配置创建 API 日志器；重复导入或热重载时不重复挂载处理器。"""
    logger = logging.getLogger(LOGGER_NAME)
    if any(getattr(handler, "_petro_agent_api_handler", False) for handler in logger.handlers):
        return logger

    configured_dir = log_dir or Path(os.getenv("PETRO_AGENT_LOG_DIR", "outputs/logs"))
    if not configured_dir.is_absolute():
        configured_dir = project_root / configured_dir
    configured_dir.mkdir(parents=True, exist_ok=True)

    file_name = Path(os.getenv("PETRO_AGENT_API_LOG_FILE", "api_calls.log")).name
    max_bytes = max(1024, int(os.getenv("PETRO_AGENT_LOG_MAX_BYTES", str(10 * 1024 * 1024))))
    backup_count = max(1, int(os.getenv("PETRO_AGENT_LOG_BACKUP_COUNT", "5")))
    record_limit = max_records or max(1, int(os.getenv("PETRO_AGENT_LOG_MAX_RECORDS", "1000")))
    handler = RecordCountingRotatingFileHandler(
        configured_dir / file_name,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        max_records=record_limit,
    )
    handler.setFormatter(JsonLineFormatter())
    # 自定义标记用于识别自身处理器，避免 uvicorn 热重载后同一请求写入多次。
    handler._petro_agent_api_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, os.getenv("PETRO_AGENT_LOG_LEVEL", "INFO").upper(), logging.INFO))
    logger.propagate = False
    return logger
