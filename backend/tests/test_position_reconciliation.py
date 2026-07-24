from app.services.position_reconciliation import reconciliation_status


def test_matching_position_is_within_tolerance() -> None:
    status, _ = reconciliation_status(0.001, 0.001000000001)
    assert status == "matched"


def test_external_balance_is_detected() -> None:
    status, _ = reconciliation_status(0.002, 0.001)
    assert status == "external_balance"


def test_strategy_record_shortfall_is_detected() -> None:
    status, _ = reconciliation_status(0.0005, 0.001)
    assert status == "shortfall"
