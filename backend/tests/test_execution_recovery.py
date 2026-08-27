from app.trading.execution_recovery import live_recovery_status


def test_stale_buy_with_positive_balance_difference_requires_confirmation() -> None:
    assert live_recovery_status("buy", 0.001) == "uncertain"


def test_stale_sell_with_negative_balance_difference_requires_confirmation() -> None:
    assert live_recovery_status("sell", -0.001) == "uncertain"


def test_stale_order_without_matching_balance_difference_is_failed() -> None:
    assert live_recovery_status("buy", 0.0) == "failed"
    assert live_recovery_status("sell", 0.001) == "failed"
