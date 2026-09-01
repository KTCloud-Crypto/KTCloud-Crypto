from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.identity.telegram_link import link_telegram_chat


router = APIRouter(prefix="/internal/telegram-links", tags=["Identity Internal"])


class TelegramLinkRequest(BaseModel):
    code: str
    chat_id: str


class TelegramLinkResponse(BaseModel):
    linked: bool


@router.post("", response_model=TelegramLinkResponse)
def link_telegram_account(
    payload: TelegramLinkRequest,
    db: Session = Depends(get_db),
) -> TelegramLinkResponse:
    """Notification worker 전용 Telegram 연결 command입니다.

    이 endpoint는 Compose 내부 network에서만 사용하며, 사용자/연결 코드 WRITE는
    Identity 서비스 안의 application service가 수행합니다.
    """
    return TelegramLinkResponse(
        linked=link_telegram_chat(db, payload.code, payload.chat_id),
    )
