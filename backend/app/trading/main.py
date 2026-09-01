from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import RequestContextMiddleware
from app.trading.api import internal_router, router as trading_router
from app.trading.api_paper import router as paper_router
from app.trading.api_trades import router as trades_router


configure_logging("trading-api")
app = FastAPI(title="SignalTrade Trading API", version="1.0.0", docs_url=None if settings.is_production else "/docs", redoc_url=None if settings.is_production else "/redoc", openapi_url=None if settings.is_production else "/openapi.json")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(RequestContextMiddleware)
app.include_router(health_router)
app.include_router(trading_router)
app.include_router(trades_router)
app.include_router(paper_router)
app.include_router(internal_router)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
