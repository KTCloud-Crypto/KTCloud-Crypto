import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.users import (
    AccountStatusOut,
    ExchangeKeyDeleteIn,
    ExchangeKeyIn,
    PasswordChangeIn,
    TelegramLinkCodeOut,
    UserOut,
    UserUpdateIn,
)
from app.services.crypto import encrypt
from app.services.security import (
    SimpleRateLimiter,
    hash_password,
    security_event_logger,
    verify_password,
)
from app.services.upbit import UpbitApiKeyValidationError, validate_upbit_api_key

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

sensitive_action_limiter = SimpleRateLimiter(
    window_seconds=settings.sensitive_endpoint_rate_limit_window_seconds,
    max_requests=settings.sensitive_endpoint_rate_limit_max_requests,
)

def _user_out(db: Session, user: User) -> UserOut:
    """상단바 준비 상태 표시에 필요한 API 키 등록 여부까지 채워 반환합니다."""
    has_api_key = (
        db.query(ApiKey.id).filter(ApiKey.user_id == user.id).first() is not None
    )
    return UserOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        telegram_chat_id=user.telegram_chat_id,
        bot_enabled=user.bot_enabled,
        execution_mode=user.execution_mode,
        live_trading_enabled=user.live_trading_enabled,
        has_api_key=has_api_key,
    )

@router.get("/me", response_model=UserOut)
def read_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    """내 프로필을 조회합니다."""
    return _user_out(db, current_user)


@router.put("/me", response_model=UserOut)
def update_me(
    payload: UserUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """닉네임, 자동매매 활성화 여부와 실행 모드를 수정합니다."""
    if payload.nickname is not None:
        current_user.nickname = payload.nickname
    if payload.bot_enabled is not None:
        current_user.bot_enabled = payload.bot_enabled
    if payload.execution_mode is not None:
        current_user.execution_mode = payload.execution_mode
    if payload.live_trading_enabled is not None:
        current_user.live_trading_enabled = payload.live_trading_enabled
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/telegram-link-code", response_model=TelegramLinkCodeOut)
def create_telegram_link_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TelegramLinkCodeOut:
    """텔레그램 계정 연결에 사용할 장기 유효 일회용 코드를 발급합니다."""
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="텔레그램 봇이 아직 설정되지 않았습니다.",
        )

    expires_at = datetime.utcnow() + timedelta(days=3650)

    for _ in range(10):
        code = f"{secrets.randbelow(1_000_000):06d}"
        exists = db.query(User.id).filter(User.telegram_link_code == code).first()
        if exists is None:
            break
    else:
        raise RuntimeError("텔레그램 연동 코드를 생성할 수 없습니다.")

    # 새 코드 발급 시 기존 연동 자동 해제
    current_user.telegram_chat_id = None
    current_user.telegram_link_code = code
    current_user.telegram_link_expires_at = expires_at
    db.commit()

    return TelegramLinkCodeOut(
        code=code,
        expires_at=expires_at,
        bot_username=settings.telegram_bot_username or None,
    )


@router.get("/me/telegram-link-code", response_model=TelegramLinkCodeOut | None)
def read_telegram_link_code(
    current_user: User = Depends(get_current_user),
) -> TelegramLinkCodeOut | None:
    """마지막으로 발급한 텔레그램 연동 코드를 다시 표시합니다."""
    if not current_user.telegram_link_code or not current_user.telegram_link_expires_at:
        return None
    return TelegramLinkCodeOut(
        code=current_user.telegram_link_code,
        expires_at=current_user.telegram_link_expires_at,
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
    if not sensitive_action_limiter.allow(f"user:{current_user.id}:exchange-key"):
        raise HTTPException(status_code=429, detail="요청이 너무 많아 잠시 후 다시 시도해 주세요.")
    try:
        validation = validate_upbit_api_key(
            payload.access_key,
            payload.secret_key,
            settings.upbit_api_base_url,
        )
    except UpbitApiKeyValidationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.message)

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


@router.get("/me/security-events", status_code=200)
def security_events(
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, Any]]]:
    """관리자/본인 확인용으로 최근 보안 이벤트를 조회합니다."""
    return {"events": security_event_logger.recent()}


@router.get("/me/status", response_model=AccountStatusOut)
def account_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountStatusOut:
    api_key = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).first()
    return AccountStatusOut(
        api_key_registered=bool(
            api_key and api_key.encrypted_access_key and api_key.encrypted_secret_key
        ),
        api_key_registered_at=api_key.created_at if api_key else None,
    )


@router.delete("/me/exchange-key", status_code=204)
def delete_exchange_key(
    payload: ExchangeKeyDeleteIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not sensitive_action_limiter.allow(f"user:{current_user.id}:delete-exchange-key"):
        raise HTTPException(status_code=429, detail="요청이 너무 많아 잠시 후 다시 시도해 주세요.")
    if not verify_password(payload.password, current_user.password):
        raise HTTPException(status_code=400, detail="비밀번호가 올바르지 않습니다.")
    current_user.bot_enabled = False
    db.query(ApiKey).filter(ApiKey.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()


@router.post("/me/password", status_code=204)
def change_password(
    payload: PasswordChangeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not sensitive_action_limiter.allow(f"user:{current_user.id}:password-change"):
        raise HTTPException(status_code=429, detail="요청이 너무 많아 잠시 후 다시 시도해 주세요.")
    if not verify_password(payload.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="새 비밀번호는 현재 비밀번호와 달라야 합니다.")
    current_user.password = hash_password(payload.new_password)
    db.commit()
