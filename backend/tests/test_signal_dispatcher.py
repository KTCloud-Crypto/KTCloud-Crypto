from types import SimpleNamespace
from unittest.mock import patch

from app.services.execution_preflight import PreflightResult
from app.services.signal_dispatcher import (
    ExecutionTarget,
    IN_FLIGHT_ORDER_STATUSES,
    PAPER_IN_FLIGHT_STATUSES,
    _prepare_live_execution,
    net_sell_proceeds,
    should_skip_live_signal,
)


class _ApiKeyQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return SimpleNamespace(id=1, user_id=7)


class _PreflightDb:
    def query(self, _model):
        return _ApiKeyQuery()


def _buy_target() -> ExecutionTarget:
    return ExecutionTarget(
        signal_id=1,
        user_strategy_id=10,
        user_id=7,
        strategy_name="이동평균 교차 전략",
        action="buy",
        market="KRW-BTC",
        price=100_000_000,
        invest_ratio=0.5,
        allocated_amount=10_000,
        execution_mode="live",
        telegram_chat_id=None,
        signal_source="strategy",
        live_trading_enabled=True,
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


def test_locked_coin_does_not_create_false_shortfall_in_order_guard() -> None:
    """주문에 묶인 코인도 소유 중이므로 balance+locked로 정합성을 판단합니다."""
    with (
        patch("app.services.signal_dispatcher._remaining_strategy_volume", return_value=0),
        patch("app.services.signal_dispatcher._has_pending_action", return_value=False),
        patch("app.services.signal_dispatcher.resolve_exchange_credentials", return_value=("a", "s")),
        patch("app.services.signal_dispatcher.get_accounts", return_value=[
            {"currency": "BTC", "balance": "0.4", "locked": "0.6"},
        ]),
        patch("app.services.signal_dispatcher.recorded_strategy_volumes", return_value={"BTC": 1.0}),
        patch(
            "app.services.signal_dispatcher.validate_order_readiness",
            return_value=PreflightResult(True, 10_000),
        ),
    ):
        result = _prepare_live_execution(_PreflightDb(), _buy_target())

    assert result.ready is True
    assert result.order_amount == 10_000


def test_real_shortfall_blocks_order_before_exchange_preflight() -> None:
    """실제 총보유량이 전략 귀속량보다 적으면 일반 주문을 공통 경로에서 차단합니다."""
    with (
        patch("app.services.signal_dispatcher._remaining_strategy_volume", return_value=0),
        patch("app.services.signal_dispatcher._has_pending_action", return_value=False),
        patch("app.services.signal_dispatcher.resolve_exchange_credentials", return_value=("a", "s")),
        patch("app.services.signal_dispatcher.get_accounts", return_value=[
            {"currency": "BTC", "balance": "0.4", "locked": "0.1"},
        ]),
        patch("app.services.signal_dispatcher.recorded_strategy_volumes", return_value={"BTC": 1.0}),
        patch("app.services.signal_dispatcher.validate_order_readiness") as validate,
    ):
        result = _prepare_live_execution(_PreflightDb(), _buy_target())

    assert result.ready is False
    assert "잔고 조정" in result.reason
    validate.assert_not_called()
