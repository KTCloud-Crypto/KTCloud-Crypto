from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# PostgreSQL 데이터베이스 연결
engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """요청마다 DB 세션을 열고 응답이 끝나면 반드시 닫습니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
