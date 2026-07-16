from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class TelegramLink(Base):
    """사용자와 텔레그램 계정을 연결하는 테이블"""

    __tablename__ = "telegram_links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    telegram_chat_id = Column(String, nullable=False, unique=True)
    telegram_username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
