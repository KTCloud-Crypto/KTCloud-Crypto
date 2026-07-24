from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from app.core.database import Base


class SupportedMarket(Base):
    """자동매매에서 선택할 수 있는 업비트 KRW 마켓."""

    __tablename__ = "supported_market"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    display_name = Column(String(50), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)


class Strategy(Base):
    """서비스에서 제공하는 자동매매 전략 카탈로그."""

    __tablename__ = "strategy"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    timeframe_minutes = Column(Integer, nullable=False)
    parameters = Column(JSON, nullable=False, default=dict)
    default_invest_ratio = Column(Float, nullable=False, default=0.2)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserStrategy(Base):
    """사용자가 선택한 전략과 사용자별 투자 비율."""

    __tablename__ = "user_strategy"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "strategy_id",
            "market_id",
            "mode",
            name="uq_user_strategy_market_mode",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategy.id"), nullable=False, index=True)
    market_id = Column(Integer, ForeignKey("supported_market.id"), nullable=False, index=True)
    mode = Column(String(16), nullable=False, default="simulated", index=True)
    invest_ratio = Column(Float, nullable=False)
    stop_loss_rate = Column(Float, nullable=True)
    take_profit_rate = Column(Float, nullable=True)
    timeframe_minutes = Column(Integer, nullable=False, default=10)
    enabled = Column(Boolean, nullable=False, default=True)
    # Telegram 등 외부 제어에서 설정을 유지한 채 신규 매수만 잠시 중단합니다.
    paused = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
