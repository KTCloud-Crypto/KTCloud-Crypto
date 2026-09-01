from __future__ import annotations

import logging

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


def link_telegram_chat(code: str, chat_id: str) -> bool:
    """Identity API에 Telegram 연결 command를 동기로 전달합니다."""
    try:
        response = httpx.post(
            f"{settings.identity_service_url.rstrip('/')}/internal/telegram-links",
            json={"code": code, "chat_id": chat_id},
            timeout=settings.identity_service_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("Identity Telegram link request failed: error=%s", type(error).__name__)
        return False
    return bool(response.json().get("linked"))
