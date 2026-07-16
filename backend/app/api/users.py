from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.users import ExchangeKeyIn, UserOut, UserUpdateIn, WebhookUrlOut
from app.services.crypto import encrypt

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    """내 프로필을 조회합니다."""
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    payload: UserUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """텔레그램 chat_id, 봇 활성화 여부를 수정합니다."""
    if payload.telegram_chat_id is not None:
        current_user.telegram_chat_id = payload.telegram_chat_id
    if payload.bot_enabled is not None:
        current_user.bot_enabled = payload.bot_enabled
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/exchange-key", status_code=204)
def set_exchange_key(
    payload: ExchangeKeyIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """거래소 API Key를 등록/갱신합니다 (암호화하여 저장)."""
    encrypted_access = encrypt(payload.access_key)
    encrypted_secret = encrypt(payload.secret_key)

    api_key = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).first()
    if api_key is None:
        db.add(
            ApiKey(
                user_id=current_user.id,
                encrypted_access_key=encrypted_access,
                encrypted_secret_key=encrypted_secret,
            )
        )
    else:
        api_key.encrypted_access_key = encrypted_access
        api_key.encrypted_secret_key = encrypted_secret
    db.commit()


@router.get("/me/webhook-url", response_model=WebhookUrlOut)
def get_webhook_url(current_user: User = Depends(get_current_user)) -> WebhookUrlOut:
    """내 전용 TradingView 웹훅 URL을 조회합니다."""
    return WebhookUrlOut(
        webhook_token=current_user.webhook_token,
        webhook_path=f"/webhook/{current_user.webhook_token}",
    )
