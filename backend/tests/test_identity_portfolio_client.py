import httpx
import pytest
from fastapi import HTTPException

from app.identity.portfolio_client import has_open_positions


def test_identity_checks_positions_through_portfolio_api(monkeypatch) -> None:
    def fake_get(url: str, **_kwargs):
        return httpx.Response(
            200,
            json=[{"subscription_id": 3}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("app.identity.portfolio_client.httpx.get", fake_get)

    assert has_open_positions(7) is True


def test_identity_returns_503_when_portfolio_check_fails(monkeypatch) -> None:
    def failing_get(*_args, **_kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("app.identity.portfolio_client.httpx.get", failing_get)

    with pytest.raises(HTTPException) as error:
        has_open_positions(7)

    assert error.value.status_code == 503
