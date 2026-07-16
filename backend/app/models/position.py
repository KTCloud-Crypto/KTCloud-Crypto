from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from app.core.database import Base


class Position(Base):
    """사용자 보유 포지션 테이블 (중복 매수/매도 방지 및 현재 상태 조회용)"""
    __tablename__ = "position"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_position_user_ticker"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    ticker = Column(String(32), nullable=False)
    status = Column(String(16), nullable=True)  # "long" or NULL
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
