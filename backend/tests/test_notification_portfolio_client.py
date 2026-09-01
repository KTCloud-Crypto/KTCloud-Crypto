import httpx

from app.notification.portfolio_client import get_open_positions, get_user_balance


def test_notification_portfolio_client_uses_internal_service_url(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_get(url: str, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return httpx.Response(
            200,
            json=[{"currency": "KRW", "balance": 1000}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("app.notification.portfolio_client.httpx.get", fake_get)

    result = get_user_balance(7)

    assert result == [{"currency": "KRW", "balance": 1000}]
    assert str(seen["url"]).endswith("/internal/portfolio/users/7/balance")


def test_notification_portfolio_client_returns_none_on_service_error(monkeypatch) -> None:
    def failing_get(*_args, **_kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("app.notification.portfolio_client.httpx.get", failing_get)

    assert get_open_positions(7) is None
