"""사용자별 활성 전략의 주문 예산을 계산합니다.
 
예산은 구독 시점의 "가용 현금"만 기준으로 산정합니다. 보유 중인 포지션은
이미 코인으로 바뀐 자산이므로 예산 계산에서 완전히 제외되며, 매도로 현금이
회수되면 그 금액이 다음 매수 예산이 됩니다.
 
전략별 비율 합계에 상한을 두지 않습니다. 실제 주문은 항상 그 시점의 가용
현금 범위 안에서만 실행되므로 잔고를 초과하는 주문은 발생하지 않습니다.
"""
 
from decimal import Decimal, ROUND_DOWN
 
from sqlalchemy.orm import Session
 
from app.models.strategy import UserStrategy
 
KRW_UNIT = Decimal("1")
 
 
def allocated_ratio(
    db: Session,
    user_id: int,
    mode: str,
    exclude_subscription_id: int | None = None,
) -> Decimal:
    """활성 전략 비율 합계입니다. 대시보드 표시용으로만 사용합니다."""
    query = db.query(UserStrategy).filter(
        UserStrategy.user_id == user_id,
        UserStrategy.mode == mode,
        UserStrategy.enabled.is_(True),
    )
    if exclude_subscription_id is not None:
        query = query.filter(UserStrategy.id != exclude_subscription_id)
    return sum((Decimal(str(item.invest_ratio)) for item in query.all()), Decimal("0"))
 
 
def reserved_amount(
    db: Session,
    user_id: int,
    mode: str,
    exclude_subscription_id: int | None = None,
    held_subscription_ids: frozenset[int] | None = None,
) -> Decimal:
    """다른 활성 전략이 확보했지만 아직 매수하지 않은 예산의 합계입니다.
 
    새 구독의 예산을 잡을 때 이 금액을 뺀 자유 현금을 기준으로 삼아야
    여러 전략의 예산 합계가 실제 현금을 넘지 않습니다.
 
    이미 매수를 마쳐 포지션을 보유한 전략은 그 금액이 현금에서 이미
    빠져나간 상태이므로 held_subscription_ids로 전달해 중복 차감을 막습니다.
    """
    query = db.query(UserStrategy).filter(
        UserStrategy.user_id == user_id,
        UserStrategy.mode == mode,
        UserStrategy.enabled.is_(True),
        UserStrategy.allocated_amount.isnot(None),
    )
    if exclude_subscription_id is not None:
        query = query.filter(UserStrategy.id != exclude_subscription_id)
 
    held = held_subscription_ids or frozenset()
    return sum(
        (
            Decimal(str(item.allocated_amount))
            for item in query.all()
            if item.id not in held
        ),
        Decimal("0"),
    )
 
 
def snapshot_allocation(
    *,
    available_cash: Decimal | float | str,
    reserved: Decimal | float | str,
    invest_ratio: Decimal | float | str,
) -> Decimal:
    """구독 시점의 자유 현금을 기준으로 주문 예산을 확정합니다.
 
    전체 현금이 아니라 다른 전략이 이미 확보한 예산을 뺀 자유 현금을 쓰므로,
    구독을 여러 개 만들어도 예산 합계가 현금을 초과하지 않습니다.
    """
    cash = max(Decimal("0"), Decimal(str(available_cash)))
    already_reserved = max(Decimal("0"), Decimal(str(reserved)))
    ratio = max(Decimal("0"), Decimal(str(invest_ratio)))
    free_cash = max(Decimal("0"), cash - already_reserved)
    return (free_cash * ratio).quantize(KRW_UNIT, rounding=ROUND_DOWN)
 
 
def budget_for_buy(
    *,
    allocated_amount: float | None,
    available_cash: Decimal | float | str,
    invest_ratio: Decimal | float | str,
) -> Decimal:
    """매수에 사용할 예산을 결정합니다.
 
    확정된 예산(allocated_amount)이 있으면 그대로 사용하고, 없으면(기존 구독)
    현재 가용 현금에 비율을 적용해 계산합니다. 어느 쪽이든 가용 현금을 넘지
    않도록 제한하므로 잔고보다 큰 주문이 나가지 않습니다.
    """
    cash = max(Decimal("0"), Decimal(str(available_cash)))
    if allocated_amount is not None:
        budget = max(Decimal("0"), Decimal(str(allocated_amount)))
    else:
        ratio = max(Decimal("0"), Decimal(str(invest_ratio)))
        budget = cash * ratio
    return min(budget, cash).quantize(KRW_UNIT, rounding=ROUND_DOWN)
 