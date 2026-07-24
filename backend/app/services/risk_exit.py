"""전략별 손절·익절 조건을 현재가와 비교해 사용자 전용 매도 신호를 생성합니다."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategySignal
from app.models.user import User
from app.services.strategy_positions import calculate_position


@dataclass(frozen=True, slots=True)
class RiskExitSignal:
    signal_id: int
    user_id: int
    mode: str


def triggered_exit_source(
    average_buy_price: float,
    current_price: float,
    stop_loss_rate: float | None,
    take_profit_rate: float | None,
) -> str | None:
    """현재 수익률이 설정 경계에 도달했을 때 기록할 매도 원인을 반환합니다."""
    return_rate = (current_price - average_buy_price) / average_buy_price
    if stop_loss_rate is not None and return_rate <= -stop_loss_rate:
        return "stop_loss"
    if take_profit_rate is not None and return_rate >= take_profit_rate:
        return "take_profit"
    return None


def create_triggered_exit_signals(db: Session, market: str, price: float) -> list[RiskExitSignal]:
    """활성 설정의 미청산 포지션을 평가하고 최초 도달한 손절·익절 신호를 저장합니다."""
    rows = (
        db.query(UserStrategy, Strategy)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .join(User, User.id == UserStrategy.user_id)
        .filter(
            SupportedMarket.code == market,
            Strategy.enabled.is_(True),
            UserStrategy.enabled.is_(True),
            User.bot_enabled.is_(True),
        )
        .all()
    )
    triggered: list[RiskExitSignal] = []
    for subscription, strategy in rows:
        if subscription.stop_loss_rate is None and subscription.take_profit_rate is None:
            continue
        pending_sell = (
            db.query(StrategyExecution.id)
            .filter(
                StrategyExecution.user_strategy_id == subscription.id,
                StrategyExecution.action == "sell",
                StrategyExecution.status.in_(["submitted", "partially_filled"]),
            )
            .first()
        )
        if pending_sell is not None:
            continue
        success_statuses = (
            frozenset({"simulated_success"})
            if subscription.mode == "simulated"
            else frozenset({"success", "partially_filled"})
        )
        executions = (
            db.query(StrategyExecution)
            .filter(
                StrategyExecution.user_strategy_id == subscription.id,
                StrategyExecution.status.in_(success_statuses),
            )
            .order_by(StrategyExecution.created_at, StrategyExecution.id)
            .all()
        )
        position = calculate_position(executions, success_statuses)
        if position.volume <= 0 or not position.average_buy_price:
            continue

        return_rate = (price - position.average_buy_price) / position.average_buy_price
        source = triggered_exit_source(
            position.average_buy_price,
            price,
            subscription.stop_loss_rate,
            subscription.take_profit_rate,
        )
        if source is None:
            continue

        signal = StrategySignal(
            strategy_id=strategy.id,
            market=market,
            timeframe_minutes=subscription.timeframe_minutes,
            action="sell",
            source=source,
            candle_open_time=datetime.utcnow(),
            close_price=price,
            metrics={
                "average_buy_price": position.average_buy_price,
                "return_rate": return_rate,
            },
        )
        db.add(signal)
        db.flush()
        triggered.append(RiskExitSignal(signal.id, subscription.user_id, subscription.mode))

    db.commit()
    return triggered
