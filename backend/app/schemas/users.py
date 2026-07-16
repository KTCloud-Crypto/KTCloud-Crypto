from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """내 프로필 조회 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    telegram_chat_id: str | None
    bot_enabled: bool


class UserUpdateIn(BaseModel):
    """내 프로필 수정 요청 스키마"""

    telegram_chat_id: str | None = None
    bot_enabled: bool | None = None


class ExchangeKeyIn(BaseModel):
    """거래소 API Key 등록/갱신 요청 스키마"""

    access_key: str = Field(..., min_length=10, max_length=255)
    secret_key: str = Field(..., min_length=10, max_length=255)


class WebhookUrlOut(BaseModel):
    """내 웹훅 URL 조회 응답 스키마"""

    webhook_token: str
    webhook_path: str
