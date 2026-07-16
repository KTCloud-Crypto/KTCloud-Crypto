from datetime import datetime

from pydantic import BaseModel


class TelegramLinkStartResponse(BaseModel):
    """텔레그램 연동용 딥링크 발급 응답"""

    deep_link: str
    token: str
    expires_in_minutes: int


class TelegramLinkConfirmRequest(BaseModel):
    """텔레그램 봇이 딥링크 클릭 후 서버로 보내는 확인 요청"""

    token: str
    telegram_chat_id: str
    telegram_username: str | None = None


class TelegramLinkConfirmResponse(BaseModel):
    """연동 확인 성공 응답"""

    message: str


class TelegramLinkStatusResponse(BaseModel):
    """현재 로그인한 사용자의 텔레그램 연동 상태"""

    linked: bool
    telegram_chat_id: str | None = None
    telegram_username: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
