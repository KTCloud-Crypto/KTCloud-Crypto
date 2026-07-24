from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.core.database import Base


class PositionSyncAdjustment(Base):
    """외부 거래로 생긴 잔고 차이를 전략 포지션에 반영한 감사 원장."""

    __tablename__ = "position_sync_adjustment"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    user_strategy_id = Column(Integer, ForeignKey("user_strategy.id"), nullable=False, index=True)
    strategy_execution_id = Column(
        Integer,
        ForeignKey("strategy_execution.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    currency = Column(String(16), nullable=False, index=True)
    action = Column(String(8), nullable=False)  # buy: 외부 수량 배정, sell: 외부 매도 차감
    volume = Column(Float, nullable=False)
    reference_price = Column(Float, nullable=False)
    difference_before = Column(Float, nullable=False)
    source = Column(String(16), nullable=False, default="web")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
