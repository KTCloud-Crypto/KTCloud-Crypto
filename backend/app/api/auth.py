from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from app.services.crypto import encrypt
from app.services.security import (
    JWTError,
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)
from app.services.upbit import UpbitApiKeyValidationError, validate_upbit_api_key

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
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

    return user


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    """사용자 계정과 Upbit API 키를 함께 등록합니다."""
    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디입니다.",
        )

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
    db.refresh(api_key)

    return SignupResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        api_key_registered_at=api_key.created_at,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """아이디와 비밀번호를 검증하고 JWT Access Token을 발급합니다."""
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 아이디입니다.",
        )

    if not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 일치하지 않습니다.",
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
def logout(current_user: User = Depends(get_current_user)) -> LogoutResponse:
    """Access Token 인증 후 로그아웃 성공 응답을 반환합니다."""
    return LogoutResponse(message=f"{current_user.username}님 로그아웃되었습니다.")
