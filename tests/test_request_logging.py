"""验证接口访问日志采用可解析的 JSONL，并能写入轮转日志文件。"""

from __future__ import annotations

import json
import logging

from petro_agent.api.request_logging import LOGGER_NAME, configure_api_logger


def test_api_logger_writes_structured_json_line(tmp_path) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    original_handlers = list(logger.handlers)
    logger.handlers.clear()
    try:
        configured = configure_api_logger(tmp_path, log_dir=tmp_path)
        configured.info(
            "接口调用完成",
            extra={
                "request_id": "request-1",
                "method": "GET",
                "path": "/api/health",
                "status_code": 200,
                "duration_ms": 1.25,
                "client_ip": "127.0.0.1",
            },
        )
        for handler in configured.handlers:
            handler.flush()

        payload = json.loads((tmp_path / "api_calls.log").read_text(encoding="utf-8"))
        assert payload["request_id"] == "request-1"
        assert payload["path"] == "/api/health"
        assert payload["status_code"] == 200
        assert payload["duration_ms"] == 1.25
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = original_handlers


def test_api_logger_rotates_after_record_limit(tmp_path) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    original_handlers = list(logger.handlers)
    logger.handlers.clear()
    try:
        configured = configure_api_logger(tmp_path, log_dir=tmp_path, max_records=2)
        for index in range(3):
            configured.info(
                "接口调用完成",
                extra={"request_id": f"request-{index}", "method": "GET", "path": "/api/health"},
            )
        for handler in configured.handlers:
            handler.flush()

        current_lines = (tmp_path / "api_calls.log").read_text(encoding="utf-8").splitlines()
        rotated_lines = (tmp_path / "api_calls.log.1").read_text(encoding="utf-8").splitlines()
        assert len(current_lines) == 1
        assert len(rotated_lines) == 2
        assert json.loads(current_lines[0])["request_id"] == "request-2"
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = original_handlers
