"""Upbit 실제 보유량과 전략 체결 기록의 수량 차이를 계산합니다."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyExecution
from app.services.strategy_positions import calculate_position

LIVE_POSITION_STATUSES = frozenset({"success", "partially_filled"})


@dataclass(frozen=True, slots=True)
class RecordedStrategyPosition:
    subscription: UserStrategy
    strategy: Strategy
    market: str
    volume: float


def recorded_strategy_positions(db: Session, user_id: int) -> list[RecordedStrategyPosition]:
    """사용자의 실전 전략별 현재 미청산 수량을 반환합니다."""
    rows = (
        db.query(UserStrategy, Strategy, SupportedMarket.code)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(UserStrategy.user_id == user_id, UserStrategy.mode == "live")
        .all()
    )
    result = []
    for subscription, strategy, market in rows:
        executions = (
            db.query(StrategyExecution)
            .filter(
                StrategyExecution.user_strategy_id == subscription.id,
                StrategyExecution.status.in_(LIVE_POSITION_STATUSES),
            )
            .order_by(StrategyExecution.created_at, StrategyExecution.id)
            .all()
        )
        position = calculate_position(executions, LIVE_POSITION_STATUSES)
        result.append(RecordedStrategyPosition(subscription, strategy, market, position.volume))
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
    tolerance = max(1e-8, strategy_volume * 1e-4)
    difference = actual_total - strategy_volume
    if abs(difference) <= tolerance:
        return "matched", "실제 잔고와 전략 기록이 일치합니다."
    if difference > 0:
        return "external_balance", "전략 기록보다 실제 잔고가 많습니다. 직접 매수한 수량이 포함됐을 수 있습니다."
    return "shortfall", "실제 잔고가 전략 기록보다 부족합니다. Upbit에서 직접 매도했는지 확인해 주세요."
