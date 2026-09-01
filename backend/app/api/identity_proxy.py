from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from starlette.responses import Response

from app.core.config import settings


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Identity Proxy"])
_HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


async def forward_internal_request(
    request: Request,
    path: str,
    *,
    service_url: str,
    service_name: str,
) -> Response:
    """Public API가 내부 서비스 응답을 상태 코드와 본문 그대로 전달합니다."""
    target_url = f"{service_url.rstrip('/')}/{path.lstrip('/')}"
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS | {"host"}
    }
    try:
        async with httpx.AsyncClient(timeout=settings.identity_service_timeout_seconds) as client:
            upstream = await client.request(
                request.method,
                target_url,
                params=request.query_params.multi_items(),
                content=await request.body(),
                headers=headers,
            )
    except httpx.RequestError as error:
        logger.warning("%s API unavailable: error=%s", service_name, type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{service_name} 서비스를 일시적으로 사용할 수 없습니다.",
        ) from error

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


async def forward_identity_request(request: Request, path: str) -> Response:
    return await forward_internal_request(
        request,
        path,
        service_url=settings.identity_service_url,
        service_name="Identity",
    )


@router.api_route(
    "/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def proxy_auth(request: Request, path: str) -> Response:
    return await forward_identity_request(request, f"auth/{path}")


@router.api_route(
    "/users/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def proxy_users(request: Request, path: str) -> Response:
    return await forward_identity_request(request, f"users/{path}")
