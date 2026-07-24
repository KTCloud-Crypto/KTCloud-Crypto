from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """내 프로필 조회 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    telegram_chat_id: str | None
    bot_enabled: bool
    execution_mode: Literal["simulated", "live"]


class UserUpdateIn(BaseModel):
    """내 프로필 수정 요청 스키마"""

    bot_enabled: bool | None = None
    execution_mode: Literal["simulated", "live"] | None = None


class ExchangeKeyIn(BaseModel):
    """거래소 API Key 등록/갱신 요청 스키마"""

    access_key: str = Field(..., min_length=10, max_length=255)
    secret_key: str = Field(..., min_length=10, max_length=255)


class TelegramLinkCodeOut(BaseModel):
    code: str
    expires_at: datetime
    bot_username: str | None
