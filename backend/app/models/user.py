from sqlalchemy import Column, Integer, String
from app.core.database import Base


class User(Base):
    """사용자 정보 테이블"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    nickname = Column(String(255), nullable=False)
