from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from app.core.database import Base


class Trade(Base):
    """매매 실행 이력 테이블"""
    __tablename__ = "trade"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    strategy_execution_id = Column(
        Integer,
        ForeignKey("strategy_execution.id"),
        unique=True,
        nullable=True,
        index=True,
    )
    ticker = Column(String(32), nullable=False)
    action = Column(String(8), nullable=False)  # buy/sell
    price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    status = Column(String(16), nullable=False)  # success/failed
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
