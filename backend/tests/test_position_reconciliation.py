import pytest

from app.main import app
from app.services.position_sync import PositionSyncError, actual_coin_totals, apply_position_sync
from app.services.position_reconciliation import calculate_reconciliation_state, reconciliation_status


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


def test_new_assign_adjustment_is_rejected_before_db_access() -> None:
    with pytest.raises(PositionSyncError, match="동기화 구분"):
        apply_position_sync(
            None,
            user_id=1,
            accounts=[],
            subscription_id=1,
            action="assign",
            volume=0.1,
            source="web",
        )


def test_assign_endpoint_is_removed_but_deduct_endpoint_remains() -> None:
    paths = app.openapi()["paths"]

    assert "/positions/reconciliation/apply" not in paths
    assert "/positions/reconciliation/deduct" in paths
