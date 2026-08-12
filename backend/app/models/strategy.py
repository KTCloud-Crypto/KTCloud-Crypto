from datetime import datetime
 
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
 
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
    # 구독 시점의 자유 잔고 x invest_ratio로 확정한 주문 예산입니다.
    # 매도가 완전 체결되면 그 매도 대금으로 갱신되어 손익이 다음 매수에 반영됩니다.
    # NULL이면 첫 매수 때 기존 총자산 비율 방식으로 산정해 채웁니다.
    allocated_amount = Column(Float, nullable=True)
    stop_loss_rate = Column(Float, nullable=True)
    take_profit_rate = Column(Float, nullable=True)
    timeframe_minutes = Column(Integer, nullable=False, default=10)
    enabled = Column(Boolean, nullable=False, default=True)
    # Telegram 등 외부 제어에서 설정을 유지한 채 신규 매수만 잠시 중단합니다.
    paused = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class StrategySubscriptionEvent(Base):
    """사용자가 전략을 시작하거나 해제한 이력을 기록합니다."""
    __tablename__ = "strategy_subscription_event"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategy.id"), nullable=False, index=True)
    market_id = Column(Integer, ForeignKey("supported_market.id"), nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)
    action = Column(String(16), nullable=False)  # "start" | "stop"
    timeframe_minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now()) 