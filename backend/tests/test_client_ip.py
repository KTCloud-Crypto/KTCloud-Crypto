from starlette.requests import Request

from app.core.client_ip import resolve_client_ip


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_trusted_proxy_uses_forwarded_client_ip() -> None:
    assert resolve_client_ip(_request("172.20.0.4", "203.0.113.10")) == "203.0.113.10"


def test_untrusted_peer_cannot_spoof_forwarded_client_ip() -> None:
    assert resolve_client_ip(_request("203.0.113.20", "198.51.100.1")) == "203.0.113.20"


def test_invalid_forwarded_ip_falls_back_to_peer() -> None:
    assert resolve_client_ip(_request("172.20.0.4", "not-an-ip")) == "172.20.0.4"
