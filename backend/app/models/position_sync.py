from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String

from app.core.database import Base


class PositionSyncAdjustment(Base):
    """외부 거래로 생긴 잔고 차이를 전략 포지션에 반영한 감사 원장."""

    __tablename__ = "position_sync_adjustment"
    __table_args__ = (
        CheckConstraint("volume > 0", name="ck_position_sync_adjustment_volume_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    user_strategy_id = Column(Integer, ForeignKey("user_strategy.id"), nullable=False, index=True)
    strategy_execution_id = Column(
        Integer,
        ForeignKey("strategy_execution.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    currency = Column(String(16), nullable=False, index=True)
    action = Column(String(8), nullable=False)  # 신규 데이터는 deduct만 생성
    volume = Column(Float, nullable=False)
    # deduct 당시 전략 평균원가. legacy assign 행의 감사 데이터도 보존합니다.
    reference_price = Column(Float, nullable=False)
    cost_basis_source = Column(String(32), nullable=False, default="strategy_average_cost")
    difference_before = Column(Float, nullable=False)
    source = Column(String(16), nullable=False, default="web")
    reason = Column(String(255), nullable=True)
    idempotency_key = Column(String(64), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
