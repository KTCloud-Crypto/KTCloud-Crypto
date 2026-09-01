from fastapi import APIRouter, Request
from starlette.responses import Response

from app.api.identity_proxy import forward_internal_request
from app.core.config import settings


router = APIRouter(tags=["Strategy Proxy"])


async def _forward(request: Request, path: str) -> Response:
    return await forward_internal_request(
        request,
        path,
        service_url=settings.strategy_service_url,
        service_name="Strategy",
    )


@router.get("/strategies", include_in_schema=False)
async def proxy_strategy_root(request: Request) -> Response:
    return await _forward(request, "strategies")


async def proxy_strategy_read(request: Request) -> Response:
    return await _forward(request, request.url.path.lstrip("/"))


for _resource in (
    "active",
    "allocation",
    "subscription-events",
    "signals",
    "reserved",
    "markets",
    "markets/tickers",
):
    router.add_api_route(
        f"/strategies/{_resource}",
        proxy_strategy_read,
        methods=["GET"],
        include_in_schema=False,
    )


@router.put("/strategies/{strategy_id}/subscription", include_in_schema=False)
async def proxy_strategy_subscription(request: Request, strategy_id: int) -> Response:
    return await _forward(request, f"strategies/{strategy_id}/subscription")


@router.post("/strategies/{strategy_id}/test-signal", include_in_schema=False)
async def proxy_strategy_test_signal(request: Request, strategy_id: int) -> Response:
    return await _forward(request, f"strategies/{strategy_id}/test-signal")
