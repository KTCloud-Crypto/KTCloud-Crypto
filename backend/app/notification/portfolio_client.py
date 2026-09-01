from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


def get_user_balance(user_id: int) -> list[dict[str, Any]] | None:
    return _get_projection(user_id, "balance")


def get_open_positions(user_id: int) -> list[dict[str, Any]] | None:
    return _get_projection(user_id, "open-positions")


def _get_projection(user_id: int, resource: str) -> list[dict[str, Any]] | None:
    try:
        response = httpx.get(
            f"{settings.portfolio_service_url.rstrip('/')}/internal/portfolio/users/{user_id}/{resource}",
            timeout=settings.identity_service_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, list) else None
    except (httpx.HTTPError, TypeError, ValueError) as error:
        logger.warning("Portfolio API %s lookup failed: error=%s", resource, type(error).__name__)
        return None
