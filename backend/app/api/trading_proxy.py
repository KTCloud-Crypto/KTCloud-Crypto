from fastapi import APIRouter, Request
from starlette.responses import Response

from app.api.identity_proxy import forward_internal_request
from app.core.config import settings


router = APIRouter(tags=["Trading Proxy"])


async def _forward(request: Request) -> Response:
    return await forward_internal_request(
        request,
        request.url.path.lstrip("/"),
        service_url=settings.trading_service_url,
        service_name="Trading",
    )


@router.get("/strategies/executions", include_in_schema=False)
async def proxy_executions(request: Request) -> Response:
    return await _forward(request)


@router.post("/strategies/liquidate-all", include_in_schema=False)
async def proxy_liquidate_all(request: Request) -> Response:
    return await _forward(request)


@router.post("/strategies/{strategy_id}/manual-sell", include_in_schema=False)
async def proxy_manual_sell(request: Request, strategy_id: int) -> Response:
    return await _forward(request)


@router.api_route("/trades", methods=["GET"], include_in_schema=False)
async def proxy_trades(request: Request) -> Response:
    return await _forward(request)


@router.api_route("/paper-account", methods=["GET", "PUT"], include_in_schema=False)
async def proxy_paper_account(request: Request) -> Response:
    return await _forward(request)


@router.api_route("/paper-account/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def proxy_paper_account_subpath(request: Request, path: str) -> Response:
    return await _forward(request)
