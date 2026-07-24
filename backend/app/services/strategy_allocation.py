"""사용자별 활성 전략의 자금 할당 비율과 주문 예산을 계산합니다."""

from decimal import Decimal, ROUND_DOWN

from sqlalchemy.orm import Session

from app.models.strategy import UserStrategy

MAX_TOTAL_ALLOCATION = Decimal("1")
KRW_UNIT = Decimal("1")


def allocated_ratio(
    db: Session,
    user_id: int,
    mode: str,
    exclude_subscription_id: int | None = None,
) -> Decimal:
    """활성 전략 비율 합계를 Decimal로 계산해 부동소수점 경계 오차를 피합니다."""
    query = db.query(UserStrategy).filter(
        UserStrategy.user_id == user_id,
        UserStrategy.mode == mode,
        UserStrategy.enabled.is_(True),
    )
    if exclude_subscription_id is not None:
        query = query.filter(UserStrategy.id != exclude_subscription_id)
    return sum((Decimal(str(item.invest_ratio)) for item in query.all()), Decimal("0"))


def allocation_within_limit(db: Session, user_id: int, mode: str) -> bool:
    return allocated_ratio(db, user_id, mode) <= MAX_TOTAL_ALLOCATION


def portfolio_buy_amount(
    *,
    total_equity: Decimal | float | str,
    available_cash: Decimal | float | str,
    invest_ratio: Decimal | float | str,
    current_position_value: Decimal | float | str = 0,
) -> Decimal:
    """전체 운용자산에서 전략 배정 한도와 현재 현금 중 작은 금액을 반환합니다.

    전략 배정 한도에서 이미 보유한 포지션 평가액을 차감하므로 향후 추가
    매수를 허용하더라도 같은 계산식을 사용할 수 있습니다.
    """
    equity = max(Decimal("0"), Decimal(str(total_equity)))
    cash = max(Decimal("0"), Decimal(str(available_cash)))
    ratio = max(Decimal("0"), Decimal(str(invest_ratio)))
    position_value = max(Decimal("0"), Decimal(str(current_position_value)))
    remaining_budget = max(Decimal("0"), equity * ratio - position_value)
    return min(remaining_budget, cash).quantize(KRW_UNIT, rounding=ROUND_DOWN)
