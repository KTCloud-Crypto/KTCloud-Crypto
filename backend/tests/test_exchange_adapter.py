from decimal import Decimal

from app.services.exchange_adapter import FakeExchangeAdapter


def test_fake_exchange_returns_deterministic_balance() -> None:
    accounts = FakeExchangeAdapter().accounts("load-access", "load-secret")

    assert accounts[0]["currency"] == "KRW"
    assert Decimal(accounts[0]["balance"]) > 0


def test_fake_exchange_market_buy_is_filled_without_network() -> None:
    result = FakeExchangeAdapter().market_buy(
        "load-access",
        "load-secret",
        "KRW-BTC",
        amount=100_000,
        reference_price=50_000_000,
    )

    assert result.status == "success"
    assert result.order_uuid.startswith("fake-")
    assert result.executed_volume == 0.002
    assert result.average_price == 50_000_000
