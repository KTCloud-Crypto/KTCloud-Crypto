from __future__ import annotations

import logging

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


async def request_manual_liquidations(*, user_id: int, subscription_ids: list[int]) -> tuple[int, list[str]] | None:
    """Telegram 확정 청산을 Trading service에 전달하고 접수 결과만 받습니다."""
    try:
        async with httpx.AsyncClient(timeout=settings.identity_service_timeout_seconds) as client:
            response = await client.post(
                f"{settings.trading_service_url.rstrip('/')}/internal/trading/users/{user_id}/manual-liquidations",
                json=subscription_ids,
            )
            response.raise_for_status()
        body = response.json()
        return int(body["requested"]), [str(name) for name in body["failures"]]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        logger.warning("Trading manual liquidation request failed: error=%s", type(error).__name__)
        return None
