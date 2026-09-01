import httpx

from fastapi import HTTPException, status

from app.core.config import settings


def disable_live_subscriptions(user_id: int) -> None:
    try:
        response = httpx.post(
            f"{settings.strategy_service_url.rstrip('/')}/internal/strategy/users/{user_id}/disable-live-subscriptions",
            timeout=settings.identity_service_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Strategy 서비스를 일시적으로 사용할 수 없습니다.",
        ) from error
