from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint

from app.core.database import Base


class StrategySignal(Base):
    """전략 엔진이 마감 캔들에서 확정한 매수·매도 신호."""

    __tablename__ = "strategy_signal"
    __table_args__ = (
        UniqueConstraint(
            "strategy_id",
            "market",
            "timeframe_minutes",
            "candle_open_time",
            "action",
            name="uq_strategy_signal_market_candle_action",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategy.id"), nullable=False, index=True)
    market = Column(String(20), nullable=False, index=True)
    timeframe_minutes = Column(Integer, nullable=False, default=10)
    action = Column(String(8), nullable=False)
    source = Column(String(16), nullable=False, default="engine")
    candle_open_time = Column(DateTime, nullable=False)
    close_price = Column(Float, nullable=False)
    metrics = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StrategyExecution(Base):
    """전략 신호의 사용자별 모의 실행, 검사 결과, 실제 주문 결과를 기록합니다."""

    __tablename__ = "strategy_execution"
    __table_args__ = (
        UniqueConstraint("signal_id", "user_strategy_id", name="uq_signal_user_strategy_execution"),
        CheckConstraint(
            "(signal_id IS NOT NULL) <> (execution_request_id IS NOT NULL)",
            name="ck_strategy_execution_single_origin",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey("strategy_signal.id"), nullable=True, index=True)
    execution_request_id = Column(
        Integer,
        ForeignKey("trading_execution_request.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    user_strategy_id = Column(Integer, ForeignKey("user_strategy.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    mode = Column(String(16), nullable=False, default="simulated", index=True)
    action = Column(String(8), nullable=False)
    market = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="simulated")
    price = Column(Float, nullable=False)
    order_amount = Column(Float, nullable=True)
    order_volume = Column(Float, nullable=True)
    order_uuid = Column(String(64), nullable=True, index=True)
    executed_volume = Column(Float, nullable=True)
    average_price = Column(Float, nullable=True)
    paid_fee = Column(Float, nullable=True)
    error_message = Column(String(500), nullable=True)
    notification_sent = Column(Boolean, nullable=False, default=False)
    settlement_notification_sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TradingExecutionRequest(Base):
    """Trading이 소유하는 사용자 수동 주문 요청입니다."""

    __tablename__ = "trading_execution_request"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    user_strategy_id = Column(Integer, ForeignKey("user_strategy.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)
    action = Column(String(8), nullable=False)
    market = Column(String(20), nullable=False)
    reference_price = Column(Float, nullable=False)
    source = Column(String(32), nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StrategyRuntime(Base):
    """전략·분봉별 가장 최근 마감 봉 계산 결과."""

    __tablename__ = "strategy_runtime"
    __table_args__ = (
        UniqueConstraint(
            "strategy_id",
            "market",
            "timeframe_minutes",
            name="uq_strategy_runtime_market_timeframe",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategy.id"), nullable=False, index=True)
    market = Column(String(20), nullable=False)
    timeframe_minutes = Column(Integer, nullable=False)
    candle_open_time = Column(DateTime, nullable=False)
    close_price = Column(Float, nullable=False)
    metrics = Column(JSON, nullable=False, default=dict)
    action = Column(String(8), nullable=True)
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
