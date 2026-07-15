from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.database import Base, engine
from app.models import User, ApiKey, TradeHistory, LastSignal

# 모든 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FastAPI Project",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(health_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello FastAPI"}
