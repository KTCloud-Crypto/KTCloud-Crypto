from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.core.database import Base


class PositionMismatchIncident(Base):
    """실제 잔고와 실전 전략 기록 사이에서 발견된 불일치 사건."""

    __tablename__ = "position_mismatch_incident"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    currency = Column(String(16), nullable=False, index=True)
    mismatch_type = Column(String(32), nullable=False, index=True)
    actual_total = Column(Float, nullable=False)
    strategy_volume = Column(Float, nullable=False)
    difference = Column(Float, nullable=False)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True, index=True)
