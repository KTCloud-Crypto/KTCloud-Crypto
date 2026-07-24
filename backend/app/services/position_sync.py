"""거래소와 전략 기록의 차이를 선택한 전략에 반영합니다."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.position_sync import PositionSyncAdjustment
from app.models.strategy_signal import StrategyExecution, StrategySignal
from app.services.position_reconciliation import recorded_strategy_positions, recorded_strategy_volumes


class PositionSyncError(ValueError):
    """현재 잔고 상태로 요청한 동기화를 적용할 수 없을 때 발생합니다."""


def actual_coin_totals(accounts: list[dict]) -> dict[str, float]:
    """Upbit 계좌 응답을 화폐별 총수량(balance + locked)으로 변환합니다."""
    return {
        item["currency"]: float(item["balance"]) + float(item["locked"])
        for item in accounts
        if item["currency"] != "KRW"
    }


def apply_position_sync(
    db: Session,
    *,
    user_id: int,
    accounts: list[dict],
    subscription_id: int,
    action: str,
    volume: float,
    source: str,
) -> PositionSyncAdjustment:
    """실제 주문 없이 외부 거래 차이를 전략 체결 기록과 감사 원장에 반영합니다."""
    if action not in {"buy", "sell"} or volume <= 0:
        raise PositionSyncError("동기화 구분 또는 수량이 올바르지 않습니다.")

    positions = recorded_strategy_positions(db, user_id)
    selected = next(
        (item for item in positions if item.subscription.id == subscription_id),
        None,
    )
    if selected is None:
        raise PositionSyncError("실전 전략 설정을 찾을 수 없습니다.")

    currency = selected.market.split("-", maxsplit=1)[-1]
    actual_total = actual_coin_totals(accounts).get(currency, 0.0)
    strategy_total = recorded_strategy_volumes(db, user_id).get(currency, 0.0)
    difference = actual_total - strategy_total
    tolerance = max(1e-8, abs(difference) * 1e-6)

    if abs(difference) <= tolerance:
        raise PositionSyncError("현재 조정할 잔고 차이가 없습니다.")
    if action == "buy":
        if difference <= 0:
            raise PositionSyncError("외부 매수 수량이 있는 경우에만 전략에 배정할 수 있습니다.")
        if volume > difference + tolerance:
            raise PositionSyncError("배정 수량이 외부 보유 수량보다 큽니다.")
    else:
        if difference >= 0:
            raise PositionSyncError("실제 잔고 부족 수량이 있는 경우에만 차감할 수 있습니다.")
        if volume > -difference + tolerance:
            raise PositionSyncError("차감 수량이 실제 잔고 부족 수량보다 큽니다.")
        if volume > selected.volume + tolerance:
            raise PositionSyncError("선택한 전략의 보유 수량보다 많이 차감할 수 없습니다.")

    account = next((item for item in accounts if item["currency"] == currency), None)
    reference_price = float(account["avg_buy_price"]) if account else 0.0
    signal = StrategySignal(
        strategy_id=selected.strategy.id,
        market=selected.market,
        timeframe_minutes=selected.subscription.timeframe_minutes,
        action=action,
        source="external_sync",
        candle_open_time=datetime.utcnow(),
        close_price=reference_price,
        metrics={"difference_before": difference, "sync_volume": volume},
    )
    db.add(signal)
    db.flush()
    execution = StrategyExecution(
        signal_id=signal.id,
        user_strategy_id=selected.subscription.id,
        user_id=user_id,
        mode="live",
        action=action,
        market=selected.market,
        status="success",
        price=reference_price,
        executed_volume=volume,
        average_price=reference_price,
    )
    db.add(execution)
    db.flush()
    # worker 중단 중 실제 체결된 것으로 추정돼 보류한 주문은 사용자의
    # 명시적 잔고 동기화가 끝나면 더 이상 후속 주문을 막지 않습니다.
    uncertain = (
        db.query(StrategyExecution)
        .filter(
            StrategyExecution.user_strategy_id == selected.subscription.id,
            StrategyExecution.action == action,
            StrategyExecution.status == "uncertain",
        )
        .all()
    )
    for item in uncertain:
        item.status = "reconciled"
        item.error_message = "실제 잔고 차이를 사용자가 전략 포지션에 동기화했습니다."
    adjustment = PositionSyncAdjustment(
        user_id=user_id,
        user_strategy_id=selected.subscription.id,
        strategy_execution_id=execution.id,
        currency=currency,
        action=action,
        volume=volume,
        reference_price=reference_price,
        difference_before=difference,
        source=source,
    )
    db.add(adjustment)
    db.commit()
    return adjustment
