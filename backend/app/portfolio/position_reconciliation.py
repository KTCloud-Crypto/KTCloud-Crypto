"""Upbit 실제 보유량과 전략 체결 기록의 수량 차이를 계산합니다."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.portfolio.strategy_positions import load_strategy_position

@dataclass(frozen=True, slots=True)
class RecordedStrategyPosition:
    subscription: UserStrategy
    strategy: Strategy
    market: str
    volume: float
    cost_basis: float
    average_buy_price: float | None


@dataclass(frozen=True, slots=True)
class ReconciliationState:
    actual_total: float
    strategy_volume: float
    difference: float
    unallocated_volume: float
    shortfall_volume: float
    status: str


def actual_coin_totals(accounts: list[dict]) -> dict[str, float]:
    """Upbit 계좌 응답을 화폐별 총수량(balance + locked)으로 변환합니다."""
    return {
        item["currency"]: float(item["balance"]) + float(item["locked"])
        for item in accounts
        if item["currency"] != "KRW"
    }


def calculate_reconciliation_state(
    actual_total: float,
    strategy_volume: float,
) -> ReconciliationState:
    tolerance = max(1e-8, strategy_volume * 1e-4)
    difference = actual_total - strategy_volume
    if abs(difference) <= tolerance:
        status = "matched"
    elif difference > 0:
        status = "external_balance"
    else:
        status = "shortfall"
    return ReconciliationState(
        actual_total=actual_total,
        strategy_volume=strategy_volume,
        difference=difference,
        unallocated_volume=max(difference, 0.0),
        shortfall_volume=max(-difference, 0.0),
        status=status,
    )


def recorded_strategy_positions(db: Session, user_id: int) -> list[RecordedStrategyPosition]:
    """사용자의 실전 전략별 현재 미청산 수량을 반환합니다."""
    rows = (
        db.query(UserStrategy, Strategy, SupportedMarket.code)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(UserStrategy.user_id == user_id, UserStrategy.mode == "live")
        .filter(Strategy.code != "manual_hold_v1")
        .all()
    )
    result = []
    for subscription, strategy, market in rows:
        position = load_strategy_position(db, subscription.id, "live")
        result.append(RecordedStrategyPosition(
            subscription,
            strategy,
            market,
            position.volume,
            position.cost_basis,
            position.average_buy_price,
        ))
    return result


def recorded_strategy_volumes(db: Session, user_id: int) -> dict[str, float]:
    """활성 여부와 무관하게 실전 전략이 소유한 미청산 수량을 화폐별로 합산합니다."""
    totals: dict[str, float] = defaultdict(float)
    for item in recorded_strategy_positions(db, user_id):
        currency = item.market.split("-", maxsplit=1)[-1]
        totals[currency] += item.volume
    return dict(totals)


def reconciliation_status(actual_total: float, strategy_volume: float) -> tuple[str, str]:
    """거래소와 내부 기록 차이를 허용 오차 안에서 분류합니다."""
    # 허용 오차: 최소 0.00000001 또는 전략 수량의 0.01% 중 큰 값
    # 부동소수점 연산 오차와 Upbit API 응답의 미세한 차이를 고려
    state = calculate_reconciliation_state(actual_total, strategy_volume)
    if state.status == "matched":
        return "matched", "실제 잔고와 전략 기록이 일치합니다."
    if state.status == "external_balance":
        return "external_balance", "전략 기록보다 실제 잔고가 많습니다. 직접 매수한 수량이 포함됐을 수 있습니다."
    return "shortfall", "실제 잔고가 전략 기록보다 부족합니다. Upbit에서 직접 매도했는지 확인해 주세요."
