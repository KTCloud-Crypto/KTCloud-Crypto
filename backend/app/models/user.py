from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from app.core.database import Base


class User(Base):
    """사용자 정보 테이블"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    nickname = Column(String(255), nullable=False)

    # 자동매매 실행 on/off
    bot_enabled = Column(Boolean, default=True, nullable=False)
    # 주문 실행 모드. 실제 주문 연동 전까지 기본값은 simulated입니다.
    execution_mode = Column(String(16), default="simulated", nullable=False)
    # 텔레그램 알림 대상 chat_id
    telegram_chat_id = Column(String(64), nullable=True)
    telegram_link_code = Column(String(16), unique=True, index=True, nullable=True)
    telegram_link_expires_at = Column(DateTime, nullable=True)
