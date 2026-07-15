from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.database import Base, engine
from app.models import User, ApiKey, TradeHistory, LastSignal

# 모든 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FastAPI Project",
    version="1.0.0",
)

app.include_router(health_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello FastAPI"}