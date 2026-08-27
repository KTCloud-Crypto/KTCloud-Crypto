"""사용자별 활성 전략의 주문 예산을 계산합니다.

예산은 구독 시점의 "가용 현금"만 기준으로 산정합니다. 실제 전략 BUY로 생긴
포지션은 이미 현금 잔고에 반영됐으므로 예약액을 다시 빼지 않습니다.

전략별 비율 합계에 상한을 두지 않습니다. 실제 주문은 항상 그 시점의 가용
현금 범위 안에서만 실행되므로 잔고를 초과하는 주문은 발생하지 않습니다.
"""
 
from decimal import Decimal, ROUND_DOWN
 
from sqlalchemy.orm import Session
 
from app.models.strategy import UserStrategy
from app.portfolio.strategy_positions import load_strategy_position
 
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
 
 
def cash_funded_subscription_ids(db: Session, user_id: int, mode: str) -> frozenset[int]:
    """최종 전략 포지션으로 예산이 현금에서 빠져나간 구독의 ID를 모읍니다.

    실제 BUY/SELL뿐 아니라 외부 매도 후 deduct까지 반영한 최종 포지션을
    사용해야, 차감으로 포지션이 0이 된 전략의 다음 매수 예산도 다시 예약됩니다.
    """
    subscriptions = db.query(UserStrategy).filter(
        UserStrategy.user_id == user_id,
        UserStrategy.mode == mode,
    ).all()
 
    held: set[int] = set()
    for subscription in subscriptions:
        if load_strategy_position(db, subscription.id, mode).volume > 0:
            held.add(subscription.id)
    return frozenset(held)
 
 
def reserved_amount(
    db: Session,
    user_id: int,
    mode: str,
    exclude_subscription_id: int | None = None,
    cash_funded_ids: frozenset[int] | None = None,
) -> Decimal:
    """다른 활성 전략이 확보했지만 아직 매수하지 않은 예산의 합계입니다.
 
    새 구독의 예산을 잡을 때 이 금액을 뺀 자유 현금을 기준으로 삼아야
    여러 전략의 예산 합계가 실제 현금을 넘지 않습니다.
 
    cash_funded_ids를 넘기지 않으면 이 함수가 직접 조회합니다.
    """
    query = db.query(UserStrategy).filter(
        UserStrategy.user_id == user_id,
        UserStrategy.mode == mode,
        UserStrategy.enabled.is_(True),
        UserStrategy.allocated_amount.isnot(None),
    )
    if exclude_subscription_id is not None:
        query = query.filter(UserStrategy.id != exclude_subscription_id)
 
    spent = (
        cash_funded_subscription_ids(db, user_id, mode)
        if cash_funded_ids is None
        else cash_funded_ids
    )
    return sum(
        (
            Decimal(str(item.allocated_amount))
            for item in query.all()
            if item.id not in spent
        ),
        Decimal("0"),
    )
 
 
# 예약 금액을 잡을 때 미리 떼어둘 매수 수수료 여유분입니다. 실제 주문 시점에는
# execution_preflight가 종목별 실제 수수료율로 다시 계산하므로, 여기서는 현금
# 전액을 예약해 두었다가 수수료 때문에 주문이 줄어드는 상황만 막으면 됩니다.
FEE_BUFFER_RATE = Decimal("0.0005")
 
 
def available_for_order(
    cash_balance: Decimal | float | str,
    reserved: Decimal | float | str,
    reserve_fee: bool = False,
) -> Decimal:
    """확보된 예산을 뺀 주문 가능 현금입니다.
 
    reserve_fee=True면 매수 수수료 여유분까지 미리 제외합니다. 새 예산을
    산정할 때 이 옵션을 켜면, 예약 금액과 실제 주문 금액이 수수료 때문에
    어긋나는 것을 막을 수 있습니다.
    """
    cash = max(Decimal("0"), Decimal(str(cash_balance)))
    already_reserved = max(Decimal("0"), Decimal(str(reserved)))
    free_cash = max(Decimal("0"), cash - already_reserved)
    if reserve_fee:
        free_cash = free_cash / (Decimal("1") + FEE_BUFFER_RATE)
    return free_cash.quantize(KRW_UNIT, rounding=ROUND_DOWN)
 
 
def allocation_from_free_cash(
    *,
    free_cash: Decimal | float | str,
    invest_ratio: Decimal | float | str,
) -> Decimal:
    """구독 시점의 자유 현금을 기준으로 주문 예산을 확정합니다.
 
    전체 현금이 아니라 다른 전략이 이미 확보한 예산을 뺀 자유 현금을 쓰므로,
    구독을 여러 개 만들어도 예산 합계가 현금을 초과하지 않습니다.
    """
    ratio = max(Decimal("0"), Decimal(str(invest_ratio)))
    available = max(Decimal("0"), Decimal(str(free_cash)))
    return (available * ratio).quantize(KRW_UNIT, rounding=ROUND_DOWN)
 
 
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
