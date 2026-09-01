from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.trading.execution_preflight import PreflightResult
from app.trading.allocation_events import enqueue_allocation_changed
from app.trading.signal_dispatcher import (
    ExecutionTarget,
    IN_FLIGHT_ORDER_STATUSES,
    PAPER_IN_FLIGHT_STATUSES,
    _create_execution_and_notify,
    _allocation_changed_amount,
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


def test_settled_order_emits_allocation_value_without_writing_subscription() -> None:
    buy = replace(_buy_target(), allocated_amount=None)
    buy_execution = SimpleNamespace(status="success", order_amount=12_345)
    sell = replace(_buy_target(), action="sell")
    sell_execution = SimpleNamespace(
        status="success", executed_volume=2, average_price=100, paid_fee=0.3
    )

    assert _allocation_changed_amount(buy, buy_execution) == 12_345
    assert _allocation_changed_amount(sell, sell_execution) == 199.7


def test_allocation_event_uses_execution_as_idempotency_key() -> None:
    db = MagicMock()
    execution = SimpleNamespace(id=41, user_strategy_id=10)

    message = enqueue_allocation_changed(db, execution, allocated_amount=12_345)

    assert message.message_type == "AllocationChanged"
    assert message.idempotency_key == "execution-allocation:41"
    assert message.payload == {
        "execution_id": 41,
        "user_strategy_id": 10,
        "allocated_amount": 12_345,
    }


def test_locked_coin_does_not_create_false_shortfall_in_order_guard() -> None:
    """주문에 묶인 코인도 소유 중이므로 balance+locked로 정합성을 판단합니다."""
    with (
        patch("app.trading.signal_dispatcher._remaining_strategy_volume", return_value=0),
        patch("app.trading.signal_dispatcher._has_pending_action", return_value=False),
        patch("app.trading.signal_dispatcher.resolve_exchange_credentials", return_value=("a", "s")),
        patch("app.trading.signal_dispatcher.get_accounts", return_value=[
            {"currency": "BTC", "balance": "0.4", "locked": "0.6"},
        ]),
        patch("app.trading.signal_dispatcher.recorded_strategy_volumes", return_value={"BTC": 1.0}),
        patch(
            "app.trading.signal_dispatcher.validate_order_readiness",
            return_value=PreflightResult(True, 10_000),
        ),
    ):
        result = _prepare_live_execution(_PreflightDb(), _buy_target())

    assert result.ready is True
    assert result.order_amount == 10_000


def test_real_shortfall_blocks_order_before_exchange_preflight() -> None:
    """실제 총보유량이 전략 귀속량보다 적으면 일반 주문을 공통 경로에서 차단합니다."""
    with (
        patch("app.trading.signal_dispatcher._remaining_strategy_volume", return_value=0),
        patch("app.trading.signal_dispatcher._has_pending_action", return_value=False),
        patch("app.trading.signal_dispatcher.resolve_exchange_credentials", return_value=("a", "s")),
        patch("app.trading.signal_dispatcher.get_accounts", return_value=[
            {"currency": "BTC", "balance": "0.4", "locked": "0.1"},
        ]),
        patch("app.trading.signal_dispatcher.recorded_strategy_volumes", return_value={"BTC": 1.0}),
        patch("app.trading.signal_dispatcher.validate_order_readiness") as validate,
    ):
        result = _prepare_live_execution(_PreflightDb(), _buy_target())

    assert result.ready is False
    assert "잔고 조정" in result.reason
    validate.assert_not_called()


def test_paused_subscription_blocks_new_buy_before_preflight() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = (
        SimpleNamespace(paused=True)
    )
    with (
        patch("app.trading.signal_dispatcher.SessionLocal", return_value=db),
        patch("app.trading.signal_dispatcher._prepare_live_execution") as prepare,
    ):
        assert _create_execution_and_notify(_buy_target()) is False

    prepare.assert_not_called()
    db.close.assert_called_once()


def test_paused_subscription_does_not_block_existing_position_sell() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = (
        SimpleNamespace(paused=True)
    )
    sell_target = replace(_buy_target(), action="sell")
    with (
        patch("app.trading.signal_dispatcher.SessionLocal", return_value=db),
        patch(
            "app.trading.signal_dispatcher._prepare_live_execution",
            return_value=PreflightResult(False, None, "no position"),
        ) as prepare,
        patch("app.trading.signal_dispatcher._create_execution", return_value=None) as create,
    ):
        assert _create_execution_and_notify(sell_target) is False

    prepare.assert_called_once()
    create.assert_called_once()
