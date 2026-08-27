"""실제 잔고보다 큰 전략 포지션을 사용자가 선택한 전략에서 차감합니다."""

from sqlalchemy.orm import Session

from app.models.position_sync import PositionSyncAdjustment
from app.models.strategy_signal import StrategyExecution
from app.portfolio.position_reconciliation import (
    actual_coin_totals,
    recorded_strategy_positions,
    recorded_strategy_volumes,
)


class PositionDeductionError(ValueError):
    """현재 잔고 상태로 요청한 전략 차감을 적용할 수 없을 때 발생합니다."""


def apply_position_deduction(
    db: Session,
    *,
    user_id: int,
    accounts: list[dict],
    subscription_id: int,
    volume: float,
    source: str,
    idempotency_key: str | None = None,
    commit: bool = True,
) -> PositionSyncAdjustment:
    """실제 주문 없이 shortfall을 전략 차감 원장에 반영합니다."""
    if volume <= 0:
        raise PositionDeductionError("차감 수량은 0보다 커야 합니다.")
    if idempotency_key:
        existing = db.query(PositionSyncAdjustment).filter(
            PositionSyncAdjustment.idempotency_key == idempotency_key,
        ).first()
        if existing is not None:
            return existing

    positions = recorded_strategy_positions(db, user_id)
    selected = next(
        (item for item in positions if item.subscription.id == subscription_id),
        None,
    )
    if selected is None:
        raise PositionDeductionError("실전 전략 설정을 찾을 수 없습니다.")

    currency = selected.market.split("-", maxsplit=1)[-1]
    actual_total = actual_coin_totals(accounts).get(currency, 0.0)
    strategy_total = recorded_strategy_volumes(db, user_id).get(currency, 0.0)
    difference = actual_total - strategy_total
    tolerance = max(1e-8, abs(difference) * 1e-6)

    if difference >= -tolerance:
        raise PositionDeductionError("실제 잔고 부족 수량이 있는 경우에만 차감할 수 있습니다.")
    if volume > -difference + tolerance:
        raise PositionDeductionError("차감 수량이 실제 잔고 부족 수량보다 큽니다.")
    if volume > selected.volume + tolerance:
        raise PositionDeductionError("선택한 전략의 보유 수량보다 많이 차감할 수 없습니다.")

    adjustment_price = float(selected.average_buy_price or 0)
    uncertain = (
        db.query(StrategyExecution)
        .filter(
            StrategyExecution.user_strategy_id == selected.subscription.id,
            StrategyExecution.action == "sell",
            StrategyExecution.status == "uncertain",
        )
        .all()
    )
    for item in uncertain:
        item.status = "reconciled"
        item.error_message = "실제 잔고 차이를 사용자가 전략 포지션에 반영했습니다."
    adjustment = PositionSyncAdjustment(
        user_id=user_id,
        user_strategy_id=selected.subscription.id,
        strategy_execution_id=None,
        currency=currency,
        action="deduct",
        volume=volume,
        reference_price=adjustment_price,
        cost_basis_source="strategy_average_cost",
        difference_before=difference,
        source=source,
        reason="실제 잔고 부족분을 전략에서 차감",
        idempotency_key=idempotency_key,
    )
    db.add(adjustment)
    db.flush()
    if commit:
        db.commit()
        db.refresh(adjustment)
    return adjustment
