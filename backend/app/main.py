from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.analytics import router as analytics_router
from app.api.health import router as health_router
from app.api.identity_proxy import router as identity_proxy_router
from app.api.strategy_proxy import router as strategy_proxy_router
from app.api.trading_proxy import router as trading_proxy_router
from app.api.portfolio_proxy import router as portfolio_proxy_router
from app.portfolio.api import reporting_router as positions_router
from app.portfolio.api import router as portfolio_router, strategy_router as portfolio_strategy_router
from app.strategy.api import router as strategy_router
from app.trading.api import router as trading_router_api
from app.trading.api_paper import router as paper_router
from app.trading.api_trades import router as trades_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import RequestContextMiddleware

configure_logging("backend")

app = FastAPI(
    title="SignalTrade API",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(identity_proxy_router)
if settings.environment.lower() == "test":
    # pytest는 별도 SQLite DB에서 API contract를 검증한다. 실제 Compose runtime은
    # 항상 strategy-api를 거쳐 Strategy handler를 실행한다.
    app.include_router(strategy_router)
    app.include_router(trading_router_api)
    app.include_router(trades_router)
    app.include_router(paper_router)
    app.include_router(portfolio_router)
    app.include_router(portfolio_strategy_router)
else:
    app.include_router(strategy_proxy_router)
    app.include_router(trading_proxy_router)
    app.include_router(portfolio_proxy_router)
app.include_router(analytics_router)
app.include_router(health_router)
app.include_router(positions_router)


@app.get("/")
async def root() -> dict[str, str]:
    """API 프로세스의 기본 식별 응답입니다. 상태 확인은 /health를 사용합니다."""
    return {"message": "SignalTrade API"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
