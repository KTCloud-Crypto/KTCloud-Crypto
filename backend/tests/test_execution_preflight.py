from decimal import Decimal
from unittest.mock import patch

from app.services.execution_preflight import (
    MIN_KRW_ORDER,
    fee_adjusted_buying_power,
    validate_order_readiness,
)
from app.services.strategy_allocation import portfolio_buy_amount


def test_portfolio_amount_is_based_on_total_equity_not_remaining_cash() -> None:
    assert portfolio_buy_amount(
        total_equity="1000000",
        available_cash="500000",
        invest_ratio=0.5,
    ) == Decimal("500000")


def test_portfolio_amount_is_capped_by_available_cash() -> None:
    assert portfolio_buy_amount(
        total_equity="1000000",
        available_cash="300000",
        invest_ratio=0.5,
    ) == Decimal("300000")


def test_existing_position_value_is_removed_from_strategy_budget() -> None:
    assert portfolio_buy_amount(
        total_equity="1000000",
        available_cash="700000",
        invest_ratio=0.5,
        current_position_value="200000",
    ) == Decimal("300000")


@patch("app.services.execution_preflight.resolve_exchange_credentials", return_value=("a", "s"))
@patch(
    "app.services.execution_preflight._buy_fee_rate",
    return_value=Decimal("0.0005"),
)
@patch(
    "app.services.execution_preflight._available_balances",
    return_value={"KRW": Decimal("500000")},
)
def test_live_preflight_includes_managed_positions_in_portfolio(
    _balances,
    _fee_rate,
    _credentials,
) -> None:
    result = validate_order_readiness(
        api_key=None,
        action="buy",
        market="KRW-BTC",
        reference_price=100_000_000,
        invest_ratio=0.5,
        managed_positions_value=500_000,
    )
    assert result.ready is True
    assert result.order_amount == 499_749


def test_buying_power_reserves_fee_and_one_won() -> None:
    amount = fee_adjusted_buying_power(
        available_krw=Decimal("6072"),
        fee_rate=Decimal("0.0005"),
    )
    assert amount == Decimal("6067")


@patch("app.services.execution_preflight.resolve_exchange_credentials", return_value=("a", "s"))
@patch(
    "app.services.execution_preflight._buy_fee_rate",
    return_value=Decimal("0.0005"),
)
@patch(
    "app.services.execution_preflight._available_balances",
    return_value={"KRW": Decimal("500000")},
)
def test_live_preflight_does_not_reduce_order_when_cash_covers_fee(
    _balances,
    _fee_rate,
    _credentials,
) -> None:
    result = validate_order_readiness(
        api_key=None,
        action="buy",
        market="KRW-BTC",
        reference_price=100_000_000,
        invest_ratio=0.5,
        managed_positions_value=300_000,
    )
    assert result.ready is True
    assert result.order_amount == 400_000


def test_minimum_krw_order_is_5000() -> None:
    assert MIN_KRW_ORDER == Decimal("5000")
