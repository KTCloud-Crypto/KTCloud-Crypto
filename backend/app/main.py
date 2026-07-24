from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.positions import router as positions_router
from app.api.trades import router as trades_router
from app.api.users import router as users_router
from app.api.strategies import router as strategies_router
from app.api.paper import router as paper_router
from app.core.database import SessionLocal
from app.services.strategy_catalog import seed_strategy_catalog

# DB 스키마는 애플리케이션 시작 전에 Alembic이 구성합니다.
with SessionLocal() as db:
    seed_strategy_catalog(db)

app = FastAPI(
    title="SignalTrade API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://34.233.225.79:5173",
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
app.include_router(strategies_router)
app.include_router(paper_router)


@app.get("/")
async def root() -> dict[str, str]:
    """API 프로세스의 기본 식별 응답입니다. 상태 확인은 /health를 사용합니다."""
    return {"message": "SignalTrade API"}
