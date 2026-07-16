import uuid
from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base


class User(Base):
    """사용자 정보 테이블"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    nickname = Column(String(255), nullable=False)

    # TradingView 웹훅 라우팅용 사용자별 고유 토큰
    webhook_token = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()), nullable=False)
    # 매매 신호 수신 on/off
    bot_enabled = Column(Boolean, default=True, nullable=False)
    # 텔레그램 알림 대상 chat_id
    telegram_chat_id = Column(String(64), nullable=True)
