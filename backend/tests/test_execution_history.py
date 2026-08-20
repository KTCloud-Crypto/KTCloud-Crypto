from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.strategy_positions import execution_trade_details


def execution(identifier: int, action: str, volume: float, price: float):
    return SimpleNamespace(
        id=identifier,
        user_strategy_id=1,
        mode="live",
        action=action,
        status="success",
        executed_volume=volume,
        average_price=price,
        price=price,
        created_at=datetime(2026, 1, 1) + timedelta(minutes=identifier),
    )


def test_sell_detail_connects_average_entry_and_exit() -> None:
    details = execution_trade_details([
        execution(1, "buy", 1, 100),
        execution(2, "buy", 1, 120),
        execution(3, "sell", 2, 130),
    ])

    assert details[1].transaction_amount == 100
    assert details[3].entry_price == 110
    assert details[3].transaction_amount == 260
    assert details[3].realized_profit_loss == pytest.approx(39.76)


def test_partial_sell_keeps_remaining_average_entry() -> None:
    details = execution_trade_details([
        execution(1, "buy", 2, 100),
        execution(2, "sell", 1, 120),
        execution(3, "sell", 1, 90),
    ])

    assert details[2].entry_price == 100
    assert details[2].realized_profit_loss == pytest.approx(19.89)
    assert details[3].entry_price == 100
    assert details[3].realized_profit_loss == pytest.approx(-10.095)


def test_deduction_reduces_cost_before_later_execution_sell() -> None:
    deducted = SimpleNamespace(
        id=1,
        user_strategy_id=1,
        action="deduct",
        volume=0.4,
        created_at=datetime(2026, 1, 1, 0, 2),
    )

    details = execution_trade_details([
        execution(1, "buy", 1, 100),
        execution(3, "sell", 0.6, 110),
    ], [deducted])

    assert details[3].entry_price == 100
    assert details[3].realized_profit_loss == pytest.approx(5.937)
