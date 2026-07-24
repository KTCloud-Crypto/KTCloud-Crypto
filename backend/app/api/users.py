import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.users import ExchangeKeyIn, TelegramLinkCodeOut, UserOut, UserUpdateIn
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
    """자동매매 활성화 여부와 실행 모드를 수정합니다."""
    if payload.bot_enabled is not None:
        current_user.bot_enabled = payload.bot_enabled
    if payload.execution_mode is not None:
        current_user.execution_mode = payload.execution_mode
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/telegram-link-code", response_model=TelegramLinkCodeOut)
def create_telegram_link_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TelegramLinkCodeOut:
    """텔레그램 계정 연결에 사용할 10분 유효 일회용 코드를 발급합니다."""
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="텔레그램 봇이 아직 설정되지 않았습니다.",
        )

    expires_at = datetime.utcnow() + timedelta(minutes=10)

    for _ in range(10):
        code = f"{secrets.randbelow(1_000_000):06d}"
        exists = db.query(User.id).filter(User.telegram_link_code == code).first()
        if exists is None:
            break
    else:
        raise RuntimeError("텔레그램 연동 코드를 생성할 수 없습니다.")

    current_user.telegram_link_code = code
    current_user.telegram_link_expires_at = expires_at
    db.commit()

    return TelegramLinkCodeOut(
        code=code,
        expires_at=expires_at,
        bot_username=settings.telegram_bot_username or None,
    )


@router.delete("/me/telegram-link", status_code=204)
def unlink_telegram(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """현재 사용자와 텔레그램 채팅 연결을 해제합니다."""
    current_user.telegram_chat_id = None
    current_user.telegram_link_code = None
    current_user.telegram_link_expires_at = None
    db.commit()


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
