from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.positions import router as positions_router
from app.api.trades import router as trades_router
from app.api.users import router as users_router
from app.api.webhook import router as webhook_router
from app.core.database import Base, engine
from app.models import User, ApiKey, Position, Trade

# 모든 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FastAPI Project",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+):517\d",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(users_router)
app.include_router(positions_router)
app.include_router(trades_router)
app.include_router(webhook_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello FastAPI"}
