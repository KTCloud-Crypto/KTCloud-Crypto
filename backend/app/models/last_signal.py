from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.core.database import Base


class LastSignal(Base):
    """마지막 신호 정보 테이블"""
    __tablename__ = "last_signal"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, unique=True)
    signal_type = Column(String(50), nullable=False)  # BUY, SELL, HOLD
    signal_time = Column(DateTime, default=datetime.utcnow, nullable=False)
