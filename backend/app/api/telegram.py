import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.telegram import TelegramLink
from app.models.user import User
from app.schemas.telegram import (
    TelegramLinkConfirmRequest,
    TelegramLinkConfirmResponse,
    TelegramLinkStartResponse,
    TelegramLinkStatusResponse,
)

router = APIRouter(
    prefix="/telegram",
    tags=["Telegram"],
)

# 토큰 -> (user_id, 만료시각) 임시 저장 (운영 전환 시 Redis 등으로 교체 권장)
_pending_tokens: dict[str, tuple[int, datetime]] = {}

TELEGRAM_BOT_USERNAME = "cryptocurrency_trading_alarmbot"
TOKEN_EXPIRE_MINUTES = 10


@router.post("/link/start", response_model=TelegramLinkStartResponse)
def start_link(
