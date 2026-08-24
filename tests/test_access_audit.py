"""验证透明 IP 审计只写 IP，并正确执行 Cloudflare 解析和滑动窗口限流。"""

from __future__ import annotations

import logging

from starlette.requests import Request

from petro_agent.api.access_audit import (
    IP_AUDIT_LOGGER_NAME,
    AccessAudit,
    configure_access_audit,
    is_page_entry_request,
    resolve_client_ip,
)


def _request(client_ip: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/health",
        "headers": headers or [],
        "client": (client_ip, 51000),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "query_string": b"",
    })


def test_resolve_client_ip_prefers_valid_cloudflare_header() -> None:
    request = _request("127.0.0.1", [(b"cf-connecting-ip", b"203.0.113.25")])
    assert resolve_client_ip(request) == "203.0.113.25"


def test_resolve_client_ip_rejects_invalid_proxy_header() -> None:
    request = _request("127.0.0.1", [(b"cf-connecting-ip", b"not-an-ip")])
    assert resolve_client_ip(request) == "127.0.0.1"


def test_only_get_root_is_treated_as_page_entry() -> None:
    base_request = _request("203.0.113.8")
    page_entry = Request({**base_request.scope, "path": "/"})
    api_request = Request({**page_entry.scope, "path": "/api/experiments"})
    asset_request = Request({**page_entry.scope, "path": "/assets/app.js"})
    head_request = Request({**page_entry.scope, "method": "HEAD"})

    assert is_page_entry_request(page_entry) is True
    assert is_page_entry_request(api_request) is False
    assert is_page_entry_request(asset_request) is False
    assert is_page_entry_request(head_request) is False


def test_ip_audit_file_contains_only_ip_and_rotates(tmp_path, monkeypatch) -> None:
    logger = logging.getLogger(IP_AUDIT_LOGGER_NAME)
    original_handlers = list(logger.handlers)
    logger.handlers.clear()
    monkeypatch.setenv("PETRO_AGENT_IP_AUDIT_LOG_FILE", "access_ip.log")
    try:
        audit = configure_access_audit(tmp_path, log_dir=tmp_path, max_records=2)
        for client_ip in ("203.0.113.1", "203.0.113.2", "203.0.113.3"):
            audit.record(client_ip)
        for handler in audit.logger.handlers:
            handler.flush()

        assert (tmp_path / "access_ip.log").read_text(encoding="utf-8").splitlines() == [
            "203.0.113.3"
        ]
        assert (tmp_path / "access_ip.log.1").read_text(encoding="utf-8").splitlines() == [
            "203.0.113.1", "203.0.113.2"
        ]
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = original_handlers


def test_rate_limit_blocks_only_after_configured_request_count() -> None:
    logger = logging.getLogger("petro_agent.test.ip_audit")
    audit = AccessAudit(logger, enabled=False, max_requests=2, window_seconds=60)

    assert audit.check_rate_limit("203.0.113.8", now=0).allowed is True
    assert audit.check_rate_limit("203.0.113.8", now=1).allowed is True
    blocked = audit.check_rate_limit("203.0.113.8", now=2)
    assert blocked.allowed is False
    assert blocked.retry_after == 58
    assert audit.check_rate_limit("203.0.113.8", now=61).allowed is True
