from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.core.database import Base


class ApiKey(Base):
    """거래소 API 키 관리 테이블 (Fernet으로 암호화하여 저장)"""
    __tablename__ = "api_key"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), unique=True, nullable=False, index=True)
    encrypted_access_key = Column(String(512), nullable=True)
    encrypted_secret_key = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
