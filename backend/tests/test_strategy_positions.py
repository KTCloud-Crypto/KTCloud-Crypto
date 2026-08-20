from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.strategy_positions import (
    PositionEvent,
    calculate_position,
    position_events_from_ledgers,
    project_position,
    project_strategy_performance,
)


def _execution(identifier: int, action: str, volume: float, price: float):
    return SimpleNamespace(
        id=identifier,
        action=action,
        status="success",
        executed_volume=volume,
        average_price=price,
        price=price,
        created_at=datetime(2026, 1, 1) + timedelta(minutes=identifier),
    )


def test_position_keeps_weighted_average_after_partial_sell() -> None:
    position = calculate_position([
        _execution(1, "buy", 2, 100),
        _execution(2, "buy", 1, 130),
        _execution(3, "sell", 1, 150),
    ])

    assert position.volume == 2
    assert position.cost_basis == 220
    assert position.average_buy_price == 110


def test_position_is_flat_after_full_sell() -> None:
    position = calculate_position([
        _execution(1, "buy", 1, 100),
        _execution(2, "sell", 1, 120),
    ])

    assert position.volume == 0
    assert position.cost_basis == 0
    assert position.average_buy_price is None


def test_assign_event_does_not_create_strategy_position() -> None:
    position = project_position([
        PositionEvent("assign", 0.2, 88_000_000, datetime(2026, 1, 1), 1),
    ])

    assert position.volume == 0
    assert position.cost_basis == 0
    assert position.average_buy_price is None


def test_deduct_reduces_volume_and_cost_without_realized_profit() -> None:
    performance = project_strategy_performance([
        PositionEvent("execution_buy", 1, 100, datetime(2026, 1, 1), 1),
        PositionEvent("deduct", 0.4, None, datetime(2026, 1, 2), 2),
    ], fee_rate=0)

    assert performance.position.volume == 0.6
    assert performance.position.cost_basis == 60
    assert performance.position.average_buy_price == 100
    assert performance.realized_profit_loss == 0


def test_strategy_performance_uses_actual_execution_fees() -> None:
    performance = project_strategy_performance([
        PositionEvent("execution_buy", 1, 100, datetime(2026, 1, 1), 1, paid_fee=0.04),
        PositionEvent("execution_sell", 1, 110, datetime(2026, 1, 2), 2, paid_fee=0.06),
    ])

    assert performance.realized_profit_loss == pytest.approx(9.9)


def test_strategy_performance_keeps_realized_profit_after_full_sell() -> None:
    performance = project_strategy_performance([
        PositionEvent("execution_buy", 1, 100_000, datetime(2026, 1, 1), 1),
        PositionEvent("execution_sell", 1, 110_000, datetime(2026, 1, 2), 2),
    ])

    assert performance.realized_profit_loss == pytest.approx(9_895)
    assert performance.sold_cost_basis == pytest.approx(100_050)


def test_strategy_performance_uses_average_cost_for_partial_sell() -> None:
    performance = project_strategy_performance([
        PositionEvent("execution_buy", 1, 100_000, datetime(2026, 1, 1), 1),
        PositionEvent("execution_buy", 1, 120_000, datetime(2026, 1, 2), 2),
        PositionEvent("execution_sell", 1, 130_000, datetime(2026, 1, 3), 3),
    ])

    assert performance.realized_profit_loss == pytest.approx(19_880)
    assert performance.sold_cost_basis == pytest.approx(110_055)


def test_legacy_external_sync_execution_and_assign_are_audit_only() -> None:
    legacy_execution = _execution(1, "buy", 0.2, 80)
    adjustment = SimpleNamespace(
        id=1,
        action="assign",
        volume=0.2,
        reference_price=80,
        created_at=legacy_execution.created_at,
    )

    events = position_events_from_ledgers(
        [(legacy_execution, "external_sync")],
        [adjustment],
        frozenset({"success"}),
    )
    position = project_position(events)

    assert position.volume == 0
    assert position.cost_basis == 0


def test_unallocated_balance_does_not_change_execution_position() -> None:
    position = project_position([
        PositionEvent("execution_buy", 0.001, 100, datetime(2026, 1, 1), 1),
        # 과거 assign 감사 이벤트가 섞여도 실제 BUY 수량만 전략 소유입니다.
        PositionEvent("assign", 0.1, 80, datetime(2026, 1, 1), 2),
    ])

    assert position.volume == 0.001
    assert position.cost_basis == 0.1
