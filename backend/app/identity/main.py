import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.exceptions import RedisError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import RequestContextMiddleware
from app.identity.api_auth import router as auth_router
from app.identity.api_internal import router as internal_router
from app.identity.api_users import router as users_router
from app.identity.redis_state import identity_security_state


configure_logging("identity-api")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    while True:
        try:
            await asyncio.to_thread(identity_security_state.ping)
            break
        except RedisError:
            logger.exception("Identity Redis unavailable; retrying startup")
            await asyncio.sleep(max(0.1, settings.redis_startup_retry_seconds))
    yield

app = FastAPI(
    title="SignalTrade Identity API",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)
app.state.readiness_checks = [identity_security_state.ping]

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(RequestContextMiddleware)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(internal_router)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
