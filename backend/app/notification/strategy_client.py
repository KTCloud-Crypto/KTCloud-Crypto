import logging

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


def set_subscriptions_paused(*, user_id: int, subscription_ids: list[int], paused: bool) -> int | None:
    try:
        response = httpx.post(
            f"{settings.strategy_service_url.rstrip('/')}/internal/strategy/subscriptions/pause",
            json={"user_id": user_id, "subscription_ids": subscription_ids, "paused": paused},
            timeout=settings.identity_service_timeout_seconds,
        )
        response.raise_for_status()
        return int(response.json()["updated"])
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        logger.warning("Strategy API pause command failed: error=%s", type(error).__name__)
        return None
