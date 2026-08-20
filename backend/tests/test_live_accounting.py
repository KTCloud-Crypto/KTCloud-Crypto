from datetime import datetime, timedelta

import pytest

from app.models.strategy_signal import StrategyExecution
from app.services.live_accounting import calculate_realized_profit


def execution(
    action: str,
    volume: float,
    price: float,
    *,
    index: int,
    status: str = "success",
) -> StrategyExecution:
    return StrategyExecution(
        id=index,
        signal_id=index,
        user_strategy_id=1,
        user_id=1,
        mode="live",
        action=action,
        market="KRW-BTC",
        status=status,
        price=price,
        executed_volume=volume,
        average_price=price,
        created_at=datetime(2026, 1, 1) + timedelta(minutes=index),
    )


def test_realized_profit_remains_after_full_sell() -> None:
    result = calculate_realized_profit([
        execution("buy", 1, 100_000, index=1),
        execution("sell", 1, 110_000, index=2),
    ])

    assert result.profit_loss == pytest.approx(9_895)
    assert result.sold_cost_basis == pytest.approx(100_050)


def test_partial_sell_uses_average_buy_cost() -> None:
    result = calculate_realized_profit([
        execution("buy", 1, 100_000, index=1),
        execution("buy", 1, 120_000, index=2),
        execution("sell", 1, 130_000, index=3),
    ])

    assert result.profit_loss == pytest.approx(19_880)
    assert result.sold_cost_basis == pytest.approx(110_055)


def test_failed_execution_is_not_included() -> None:
    result = calculate_realized_profit([
        execution("buy", 1, 100_000, index=1),
        execution("sell", 1, 110_000, index=2, status="failed"),
    ])

    assert result.profit_loss == 0
    assert result.sold_cost_basis == 0


def test_actual_paid_fee_overrides_default_fee_estimate() -> None:
    bought = execution("buy", 1, 100_000, index=1)
    sold = execution("sell", 1, 110_000, index=2)
    bought.paid_fee = 40
    sold.paid_fee = 60

    result = calculate_realized_profit([bought, sold])

    assert result.profit_loss == pytest.approx(9_900)
    assert result.sold_cost_basis == pytest.approx(100_040)
