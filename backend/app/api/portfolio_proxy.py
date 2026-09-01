from fastapi import APIRouter, Request
from starlette.responses import Response

from app.api.identity_proxy import forward_internal_request
from app.core.config import settings


router = APIRouter(tags=["Portfolio Proxy"])


async def _forward(request: Request, path: str) -> Response:
    return await forward_internal_request(
        request,
        path,
        service_url=settings.portfolio_service_url,
        service_name="Portfolio",
    )


@router.get("/strategies/positions", include_in_schema=False)
async def proxy_strategy_positions(request: Request) -> Response:
    return await _forward(request, "strategies/positions")


async def proxy_portfolio_read(request: Request) -> Response:
    return await _forward(request, request.url.path.lstrip("/"))


for _resource in ("balance", "reconciliation"):
    router.add_api_route(
        f"/positions/{_resource}",
        proxy_portfolio_read,
        methods=["GET"],
        include_in_schema=False,
    )


@router.post("/positions/reconciliation/deduct", include_in_schema=False)
async def proxy_position_deduction(request: Request) -> Response:
    return await _forward(request, "positions/reconciliation/deduct")
