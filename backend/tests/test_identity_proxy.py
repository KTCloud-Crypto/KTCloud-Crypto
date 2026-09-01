import asyncio

import httpx
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.identity_proxy import forward_identity_request
from app.core.config import settings
from app.identity.main import app as identity_app


def _request(method: str, path: str, body: bytes = b"") -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": path.split("?", 1)[0],
            "query_string": path.partition("?")[2].encode(),
            "headers": [(b"authorization", b"Bearer token"), (b"content-type", b"application/json")],
            "scheme": "http",
            "server": ("backend", 8000),
            "client": ("127.0.0.1", 50000),
        },
        receive,
    )


def test_public_api_forwards_identity_method_body_query_and_auth(monkeypatch) -> None:
    received: dict = {}

    class FakeClient:
        def __init__(self, *, timeout: float):
            received["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, method: str, url: str, **kwargs):
            received.update(method=method, url=url, **kwargs)
            return httpx.Response(
                401,
                content=b'{"detail":"invalid token"}',
                headers={"content-type": "application/json", "www-authenticate": "Bearer"},
            )

    monkeypatch.setattr("app.api.identity_proxy.httpx.AsyncClient", FakeClient)
    request = _request("POST", "/auth/login?source=web", b'{"username":"user"}')

    response = asyncio.run(forward_identity_request(request, "auth/login"))

    assert received["method"] == "POST"
    assert received["url"] == f"{settings.identity_service_url}/auth/login"
    assert received["params"] == [("source", "web")]
    assert received["content"] == b'{"username":"user"}'
    assert received["headers"]["authorization"] == "Bearer token"
    assert response.status_code == 401
    assert response.body == b'{"detail":"invalid token"}'
    assert response.headers["www-authenticate"] == "Bearer"


def test_public_api_returns_503_when_identity_is_unavailable(monkeypatch) -> None:
    class FailingClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, *_args, **_kwargs):
            raise httpx.ConnectError("down")

    monkeypatch.setattr("app.api.identity_proxy.httpx.AsyncClient", FailingClient)
    request = _request("GET", "/users/me")

    try:
        asyncio.run(forward_identity_request(request, "users/me"))
    except Exception as error:
        assert getattr(error, "status_code", None) == 503
        assert getattr(error, "detail", None) == "Identity 서비스를 일시적으로 사용할 수 없습니다."
    else:
        raise AssertionError("Identity outage must return a 503 error")


def test_identity_api_entrypoint_exposes_health() -> None:
    response = TestClient(identity_app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
