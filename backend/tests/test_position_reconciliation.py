import pytest
from types import SimpleNamespace

from app.main import app
from app.services import position_deduction, position_reconciliation
from app.services.position_deduction import PositionDeductionError, apply_position_deduction
from app.services.position_reconciliation import (
    actual_coin_totals,
    build_reconciliation_items,
    calculate_reconciliation_state,
    reconciliation_status,
)


def test_matching_position_is_within_tolerance() -> None:
    status, _ = reconciliation_status(0.001, 0.001000000001)
    assert status == "matched"


def test_external_balance_is_detected() -> None:
    status, _ = reconciliation_status(0.002, 0.001)
    assert status == "external_balance"


def test_strategy_record_shortfall_is_detected() -> None:
    status, _ = reconciliation_status(0.0005, 0.001)
    assert status == "shortfall"


def test_all_exchange_balance_is_unallocated_without_strategy_position() -> None:
    state = calculate_reconciliation_state(1.0, 0.0)

    assert state.unallocated_volume == 1.0
    assert state.shortfall_volume == 0


def test_unallocated_balance_is_derived_from_current_exchange_balance() -> None:
    assert calculate_reconciliation_state(1.0, 0.7).unallocated_volume == pytest.approx(0.3)
    assert calculate_reconciliation_state(0.8, 0.7).unallocated_volume == pytest.approx(0.1)


def test_multiple_strategy_shortfall_is_aggregate_state() -> None:
    state = calculate_reconciliation_state(0.5, 0.4 + 0.3)

    assert state.status == "shortfall"
    assert state.shortfall_volume == pytest.approx(0.2)


def test_locked_balance_counts_toward_exchange_total() -> None:
    totals = actual_coin_totals([
        {"currency": "BTC", "balance": "0.4", "locked": "0.6"},
        {"currency": "KRW", "balance": "1000", "locked": "500"},
    ])

    assert totals == {"BTC": 1.0}
    assert calculate_reconciliation_state(totals["BTC"], 1.0).status == "matched"


def test_reconciliation_response_keeps_locked_and_strategy_breakdown(monkeypatch) -> None:
    first = SimpleNamespace(
        subscription=SimpleNamespace(id=10),
        strategy=SimpleNamespace(id=1, name="SMA"),
        market="KRW-BTC",
        volume=0.4,
    )
    second = SimpleNamespace(
        subscription=SimpleNamespace(id=11),
        strategy=SimpleNamespace(id=2, name="RSI"),
        market="KRW-BTC",
        volume=0.3,
    )
    monkeypatch.setattr(
        position_reconciliation,
        "recorded_strategy_positions",
        lambda *_args: [first, second],
    )
    monkeypatch.setattr(
        position_reconciliation,
        "recorded_strategy_volumes",
        lambda *_args: {"BTC": 0.7},
    )

    items = build_reconciliation_items(None, 1, [
        {"currency": "KRW", "balance": "1000", "locked": "500"},
        {"currency": "BTC", "balance": "0.4", "locked": "0.6"},
    ])

    assert len(items) == 1
    assert items[0].currency == "BTC"
    assert items[0].actual_available == 0.4
    assert items[0].actual_locked == 0.6
    assert items[0].actual_total == 1.0
    assert items[0].strategy_volume == pytest.approx(0.7)
    assert items[0].difference == pytest.approx(0.3)
    assert items[0].status == "external_balance"
    assert [item.subscription_id for item in items[0].strategies] == [10, 11]


def test_non_positive_deduction_is_rejected_before_db_access() -> None:
    with pytest.raises(PositionDeductionError, match="0보다 커야"):
        apply_position_deduction(
            None,
            user_id=1,
            accounts=[],
            subscription_id=1,
            volume=0,
            source="web",
        )


def test_assign_endpoint_is_removed_but_deduct_endpoint_remains() -> None:
    paths = app.openapi()["paths"]

    assert "/positions/reconciliation/apply" not in paths
    assert "/positions/reconciliation/deduct" in paths


def _selected_position(volume: float = 1.0):
    return SimpleNamespace(
        subscription=SimpleNamespace(id=10),
        market="KRW-BTC",
        volume=volume,
        average_buy_price=100.0,
    )


def test_deduction_rejects_stale_request_after_shortfall_is_resolved(monkeypatch) -> None:
    monkeypatch.setattr(position_deduction, "recorded_strategy_positions", lambda *_args: [_selected_position()])
    monkeypatch.setattr(position_deduction, "recorded_strategy_volumes", lambda *_args: {"BTC": 1.0})

    with pytest.raises(PositionDeductionError, match="부족 수량이 있는 경우"):
        apply_position_deduction(
            None,
            user_id=1,
            accounts=[{"currency": "BTC", "balance": "1", "locked": "0"}],
            subscription_id=10,
            volume=0.1,
            source="web",
        )


def test_deduction_rejects_volume_larger_than_current_shortfall(monkeypatch) -> None:
    monkeypatch.setattr(position_deduction, "recorded_strategy_positions", lambda *_args: [_selected_position()])
    monkeypatch.setattr(position_deduction, "recorded_strategy_volumes", lambda *_args: {"BTC": 1.0})

    with pytest.raises(PositionDeductionError, match="부족 수량보다 큽니다"):
        apply_position_deduction(
            None,
            user_id=1,
            accounts=[{"currency": "BTC", "balance": "0.8", "locked": "0"}],
            subscription_id=10,
            volume=0.3,
            source="web",
        )


def test_deduction_rejects_volume_larger_than_selected_strategy_position(monkeypatch) -> None:
    monkeypatch.setattr(
        position_deduction,
        "recorded_strategy_positions",
        lambda *_args: [_selected_position(volume=0.2)],
    )
    monkeypatch.setattr(position_deduction, "recorded_strategy_volumes", lambda *_args: {"BTC": 1.0})

    with pytest.raises(PositionDeductionError, match="전략의 보유 수량보다"):
        apply_position_deduction(
            None,
            user_id=1,
            accounts=[{"currency": "BTC", "balance": "0", "locked": "0"}],
            subscription_id=10,
            volume=0.3,
            source="web",
        )
