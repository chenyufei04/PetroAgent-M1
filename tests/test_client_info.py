"""验证客户端地址接口只使用 ASGI 连接信息。"""

from starlette.requests import Request

from petro_agent.api.main import client_info


def test_client_info_returns_observed_client_ip() -> None:
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/api/client-info",
        "headers": [],
        "client": ("192.168.1.88", 51000),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "query_string": b"",
    })

    assert client_info(request) == {"ip_address": "192.168.1.88", "is_loopback": False}


def test_client_info_marks_loopback_address() -> None:
    request = Request({
        "type": "http", "method": "GET", "path": "/api/client-info", "headers": [],
        "client": ("127.0.0.1", 51000), "server": ("127.0.0.1", 8000),
        "scheme": "http", "query_string": b"",
    })

    assert client_info(request)["is_loopback"] is True


def test_client_info_uses_cloudflare_public_ip() -> None:
    request = Request({
        "type": "http", "method": "GET", "path": "/api/client-info",
        "headers": [(b"cf-connecting-ip", b"203.0.113.77")],
        "client": ("127.0.0.1", 51000), "server": ("127.0.0.1", 8000),
        "scheme": "http", "query_string": b"",
    })

    assert client_info(request) == {"ip_address": "203.0.113.77", "is_loopback": False}
