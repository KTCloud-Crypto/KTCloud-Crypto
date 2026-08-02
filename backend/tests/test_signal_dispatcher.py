from app.services.execution_preflight import PreflightResult
from app.services.signal_dispatcher import (
    IN_FLIGHT_ORDER_STATUSES,
    PAPER_IN_FLIGHT_STATUSES,
    should_skip_live_signal,
)


def test_live_sell_without_position_is_skipped() -> None:
    result = PreflightResult(False, None, "이 전략으로 매수해 남아 있는 수량이 없습니다.")
    assert should_skip_live_signal("sell", result) is True


def test_real_validation_error_is_not_skipped() -> None:
    result = PreflightResult(False, None, "Upbit 계좌 조회에 실패했습니다.")
    assert should_skip_live_signal("sell", result) is False


def test_ready_execution_reserves_order_slot() -> None:
    assert "ready" in IN_FLIGHT_ORDER_STATUSES
    assert "uncertain" in IN_FLIGHT_ORDER_STATUSES


def test_duplicate_in_flight_order_is_skipped_without_notification() -> None:
    result = PreflightResult(False, None, "이미 같은 방향의 주문이 접수 중입니다.")
    assert should_skip_live_signal("buy", result) is True


def test_pending_paper_execution_reserves_paper_account_slot() -> None:
    assert PAPER_IN_FLIGHT_STATUSES == frozenset({"simulated_pending"})
