import httpx

from fastapi import HTTPException, status

from app.core.config import settings


def has_open_positions(user_id: int) -> bool:
    """API key 교체 전에 Portfolio-owned 포지션 존재 여부를 확인합니다."""
    try:
        response = httpx.get(
            f"{settings.portfolio_service_url.rstrip('/')}/internal/portfolio/users/{user_id}/open-positions",
            timeout=settings.identity_service_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, list):
            raise ValueError("invalid Portfolio response")
        return bool(body)
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Portfolio 서비스를 일시적으로 사용할 수 없습니다.",
        ) from error
