from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from app.core.database import Base


class TradeHistory(Base):
    """거래 이력 테이블"""
    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    stock_name = Column(String(255), nullable=False)
    buy_amount = Column(Numeric(18, 2), nullable=True)
    sell_amount = Column(Numeric(18, 2), nullable=True)
    traded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
