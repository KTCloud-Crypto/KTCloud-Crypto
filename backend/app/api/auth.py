import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import user_id_var
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.auth import (
    LoginErrorResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    PasswordResetConfirm,
    PasswordResetMessage,
    PasswordResetRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from app.identity import (
    JWTError,
    LoginAttemptGuard,
    SimpleRateLimiter,
    create_jwt_token,
    decode_jwt_token,
    encrypt,
    hash_password,
    verify_password,
)
from app.core.audit import record_security_event
from app.notification.telegram import send_message
from app.market_data import UpbitApiKeyValidationError, validate_upbit_api_key

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)
bearer_scheme = HTTPBearer(auto_error=False)
login_attempt_guard = LoginAttemptGuard(
    max_failures=settings.login_max_failures,
    lockout_minutes=settings.login_lockout_minutes,
)
password_reset_request_limiter = SimpleRateLimiter(window_seconds=300, max_requests=3)
password_reset_confirm_limiter = SimpleRateLimiter(window_seconds=300, max_requests=10)


def _password_reset_token_hash(username: str, token: str) -> str:
    value = f"{username.lower()}:{token}".encode("utf-8")
    return hmac.new(settings.secret_key.encode("utf-8"), value, hashlib.sha256).hexdigest()


def _clear_password_reset(user: User) -> None:
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.password_reset_attempts = 0


def notify_login_lockout(user: User, lockout_minutes: int) -> None:
    """계정 잠금 시 사용자에게 텔레그램 안내를 보냅니다."""
    if not user.telegram_chat_id:
        return
    message = (
        f"🔒 계정 잠금 안내\n"
        f"비밀번호 5회 오류로 인해 계정이 {lockout_minutes}분 동안 잠금되었습니다.\n"
        f"잠시 후 다시 시도해 주세요."
    )
    send_message(user.telegram_chat_id, message)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Access Token으로 현재 사용자를 확인합니다."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_jwt_token(
            token=credentials.credentials,
            secret_key=settings.secret_key,
            expected_type="access",
        )
        user_id = int(payload.get("sub", ""))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 인증 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_var.set(user.id)
    return user


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request, db: Session = Depends(get_db)) -> SignupResponse:
    """사용자 계정을 만들고, 입력된 경우에만 Upbit API 키를 등록합니다."""
    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디입니다.",
        )

    has_exchange_key = bool(payload.access_key and payload.secret_key)
    if has_exchange_key:
        try:
            validation_result = validate_upbit_api_key(
                access_key=payload.access_key,
                secret_key=payload.secret_key,
                base_url=settings.upbit_api_base_url,
            )
        except UpbitApiKeyValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            )

        if not validation_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result.message,
            )

    user = User(
        username=payload.username,
        password=hash_password(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    db.flush()

    api_key = None
    if has_exchange_key:
        api_key = ApiKey(
            user_id=user.id,
            encrypted_access_key=encrypt(payload.access_key),
            encrypted_secret_key=encrypt(payload.secret_key),
        )
        db.add(api_key)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 계정 또는 API Key입니다.",
        )

    db.refresh(user)
    if api_key is not None:
        db.refresh(api_key)
    record_security_event(
        db, "account_created", "success", actor_user_id=user.id,
        actor_key=user.username, resource_type="user", resource_id=str(user.id), request=request,
    )

    return SignupResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        api_key_registered_at=api_key.created_at if api_key else None,
    )


@router.post("/password-reset/request", response_model=PasswordResetMessage, status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> PasswordResetMessage:
    """연결된 Telegram으로 일회용 비밀번호 재설정 코드를 보냅니다."""
    generic_message = "계정과 연결된 텔레그램이 있다면 재설정 코드를 전송했습니다."
    username = payload.username.strip()
    if not password_reset_request_limiter.allow(f"password-reset:{username.lower()}"):
        return PasswordResetMessage(message=generic_message)

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.telegram_chat_id or not settings.telegram_bot_token:
        return PasswordResetMessage(message=generic_message)

    token = f"{secrets.randbelow(100_000_000):08d}"
    user.password_reset_token_hash = _password_reset_token_hash(user.username, token)
    user.password_reset_expires_at = datetime.utcnow() + timedelta(minutes=settings.password_reset_token_expire_minutes)
    user.password_reset_attempts = 0
    db.commit()

    delivered = send_message(
        user.telegram_chat_id,
        "🔐 SignalTrade 비밀번호 재설정\n\n"
        f"인증 코드: {token}\n"
        f"유효 시간: {settings.password_reset_token_expire_minutes}분\n\n"
        "본인이 요청하지 않았다면 이 메시지를 무시하고 계정 보안을 확인해 주세요.",
    )
    if not delivered:
        _clear_password_reset(user)
        db.commit()
    return PasswordResetMessage(message=generic_message)


@router.post("/password-reset/confirm", response_model=PasswordResetMessage)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> PasswordResetMessage:
    """Telegram 일회용 코드를 검증하고 비밀번호를 변경합니다."""
    username = payload.username.strip()
    if not password_reset_confirm_limiter.allow(f"password-reset-confirm:{username.lower()}"):
        raise HTTPException(status_code=429, detail="요청이 너무 많아 잠시 후 다시 시도해 주세요.")

    user = db.query(User).filter(User.username == username).first()
    invalid = HTTPException(status_code=400, detail="인증 코드가 올바르지 않거나 만료되었습니다.")
    if user is None or not user.password_reset_token_hash or not user.password_reset_expires_at:
        raise invalid
    if user.password_reset_expires_at < datetime.utcnow():
        _clear_password_reset(user)
        db.commit()
        raise invalid
    if user.password_reset_attempts >= settings.password_reset_max_attempts:
        _clear_password_reset(user)
        db.commit()
        raise invalid

    supplied_hash = _password_reset_token_hash(user.username, payload.token)
    if not hmac.compare_digest(supplied_hash, user.password_reset_token_hash):
        user.password_reset_attempts += 1
        if user.password_reset_attempts >= settings.password_reset_max_attempts:
            _clear_password_reset(user)
        db.commit()
        raise invalid

    user.password = hash_password(payload.new_password)
    _clear_password_reset(user)
    db.commit()
    login_attempt_guard.reset(user.username)
    send_message(
        user.telegram_chat_id,
        "✅ SignalTrade 비밀번호가 재설정되었습니다. 본인이 변경하지 않았다면 즉시 관리자에게 문의해 주세요.",
    )
    return PasswordResetMessage(message="비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    """아이디와 비밀번호를 검증하고 JWT Access Token을 발급합니다."""
    if not login_attempt_guard.allow(payload.username):
        record_security_event(
            db, "login_attempt", "failure", actor_key=payload.username,
            detail="account_locked", request=request,
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=LoginErrorResponse(
                detail=f"로그인 실패가 너무 많아 {settings.login_lockout_minutes}분 동안 잠금되었습니다.",
                remaining_attempts=0,
                max_attempts=settings.login_max_failures,
                lockout_minutes=settings.login_lockout_minutes,
            ).model_dump(),
        )

    user = db.query(User).filter(User.username == payload.username).first()
    if user is None:
        login_attempt_guard.record_failure(payload.username)
        record_security_event(
            db, "login_attempt", "failure", actor_key=payload.username,
            detail="unknown_user", request=request,
        )
        remaining_attempts = max(0, settings.login_max_failures - len(login_attempt_guard._failures.get(payload.username, [])))
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=LoginErrorResponse(
                detail="존재하지 않는 아이디입니다.",
                remaining_attempts=remaining_attempts,
                max_attempts=settings.login_max_failures,
            ).model_dump(),
        )

    if not verify_password(payload.password, user.password):
        login_attempt_guard.record_failure(payload.username)
        remaining_attempts = max(0, settings.login_max_failures - len(login_attempt_guard._failures.get(payload.username, [])))
        failed_attempts = settings.login_max_failures - remaining_attempts
        if login_attempt_guard.is_locked(payload.username):
            notify_login_lockout(user, settings.login_lockout_minutes)
        record_security_event(
            db, "login_attempt", "failure", actor_user_id=user.id,
            actor_key=user.username, detail="invalid_password", request=request,
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=LoginErrorResponse(
                detail=f"비밀번호가 올바르지 않습니다. ({failed_attempts}/{settings.login_max_failures})",
                remaining_attempts=remaining_attempts,
                max_attempts=settings.login_max_failures,
                lockout_minutes=settings.login_lockout_minutes if remaining_attempts == 0 else None,
            ).model_dump(),
        )

    login_attempt_guard.reset(payload.username)
    user_id_var.set(user.id)
    record_security_event(
        db, "login_attempt", "success", actor_user_id=user.id,
        actor_key=user.username, resource_type="user", resource_id=str(user.id), request=request,
    )

    access_token = create_jwt_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        token_type="access",
    )

    return LoginResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        token=TokenResponse(access_token=access_token),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LogoutResponse:
    """Access Token 인증 후 로그아웃 성공 응답을 반환합니다."""
    record_security_event(
        db, "logout", "success", actor_user_id=current_user.id,
        actor_key=current_user.username, resource_type="user", resource_id=str(current_user.id), request=request,
    )
    return LogoutResponse(message=f"{current_user.username}님 로그아웃되었습니다.")
