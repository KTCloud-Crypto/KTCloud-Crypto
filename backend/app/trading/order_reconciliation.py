"""접수 후 미완료인 Upbit 주문을 재조회해 최종 상태를 DB와 알림에 반영합니다."""

import logging

from app.core.database import SessionLocal
from app.models.api_key import ApiKey
from app.models.strategy import Strategy, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategySignal
from app.models.trade import Trade
from app.models.user import User
from app.identity import resolve_exchange_credentials
from app.trading.live_order import fetch_order_result
from app.messaging.notification_events import enqueue_notification_requested

logger = logging.getLogger(__name__)
PENDING_STATUSES = ("submitted", "partially_filled")
FINAL_STATUSES = {"success", "cancelled", "failed"}


def reconcile_pending_orders() -> int:
    """미완료 주문을 한 차례 조회하고 최종 상태로 바뀐 주문 수를 반환합니다."""
    db = SessionLocal()
    settled = 0
    try:
        rows = (
            db.query(StrategyExecution, StrategySignal, Strategy, User)
            .outerjoin(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
            .join(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
            .join(Strategy, Strategy.id == UserStrategy.strategy_id)
            .join(User, User.id == StrategyExecution.user_id)
            .filter(
                StrategyExecution.status.in_(PENDING_STATUSES),
                StrategyExecution.order_uuid.isnot(None),
            )
            .all()
        )
        for execution, signal, strategy, user in rows:
            api_key = db.query(ApiKey).filter(ApiKey.user_id == execution.user_id).first()
            try:
                access_key, secret_key = resolve_exchange_credentials(api_key)
            except ValueError as error:
                logger.warning("Pending order credentials unavailable: execution=%s error=%s", execution.id, error)
                continue

            result = fetch_order_result(
                access_key=access_key,
                secret_key=secret_key,
                order_uuid=execution.order_uuid,
            )
            if result is None:
                continue

            previous_status = execution.status
            execution.status = result.status
            execution.executed_volume = result.executed_volume
            execution.average_price = result.average_price
            execution.paid_fee = result.paid_fee
            execution.error_message = result.error_message

            trade = db.query(Trade).filter(Trade.strategy_execution_id == execution.id).first()
            if trade is not None:
                trade.status = result.status
                trade.volume = result.executed_volume
                trade.price = result.average_price or execution.price
                trade.raw_response = result.raw_response

            if result.status in FINAL_STATUSES and previous_status not in FINAL_STATUSES:
                settled += 1
                if not execution.settlement_notification_sent:
                    text = _settlement_message(execution, signal.source if signal else "manual", strategy)
                    if enqueue_notification_requested(
                        db,
                        chat_id=user.telegram_chat_id,
                        message=text,
                        producer="trading-worker",
                        notification_type="order_settlement",
                        user_id=user.id,
                        idempotency_key=f"execution-settlement:{execution.id}",
                    ):
                        execution.settlement_notification_sent = True
            db.commit()
        return settled
    finally:
        db.close()


def _settlement_message(
    execution: StrategyExecution,
    signal_source: str,
    strategy: Strategy,
) -> str:
    action = "매수" if execution.action == "buy" else "매도"
    reason = {
        "stop_loss": "손절 조건 도달",
        "take_profit": "목표 수익률 도달",
        "manual": "사용자 수동 매도",
    }.get(signal_source)
    reason_line = f"매도 사유: {reason}\n" if execution.action == "sell" and reason else ""
    if execution.status == "success":
        return (
            f"✅ [실전 체결 완료] {action}\n\n"
            f"📌 전략: {strategy.name}\n🪙 종목: {execution.market}\n"
            f"💵 평균 체결가: {execution.average_price or execution.price:,.0f}원\n"
            f"📦 체결수량: {execution.executed_volume or 0:.8f}\n"
            f"{reason_line}🔑 주문 UUID: {execution.order_uuid}"
        )
    return (
        f"⚠️ [실전 주문 종료] {action}\n\n"
        f"📌 전략: {strategy.name}\n🪙 종목: {execution.market}\n"
        f"📊 상태: {execution.status}\n"
        f"⚠️ 사유: {execution.error_message or '체결 없이 주문이 종료되었습니다.'}\n"
        f"🔑 주문 UUID: {execution.order_uuid}"
    )
