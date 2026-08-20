from types import SimpleNamespace

from app.services.execution_preflight import PreflightResult
from app.services.signal_dispatcher import (
    IN_FLIGHT_ORDER_STATUSES,
    PAPER_IN_FLIGHT_STATUSES,
    net_sell_proceeds,
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


def test_ready_buy_is_not_blocked_by_exchange_only_balance() -> None:
    # dispatcher의 BUY 차단 입력은 중앙 Strategy Position뿐입니다. 거래소의
    # 미배정 보유량은 preflight 결과를 실패로 바꾸지 않습니다.
    assert should_skip_live_signal("buy", PreflightResult(True, 10_000)) is False


def test_pending_paper_execution_reserves_paper_account_slot() -> None:
    assert PAPER_IN_FLIGHT_STATUSES == frozenset({"simulated_pending"})


def test_next_budget_uses_actual_net_sell_proceeds() -> None:
    execution = SimpleNamespace(
        executed_volume=2,
        average_price=100,
        paid_fee=0.3,
    )

    assert net_sell_proceeds(execution, 90) == 199.7
