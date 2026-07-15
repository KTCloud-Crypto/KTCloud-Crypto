from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.auth import SignupRequest, SignupResponse
from app.services.security import hash_password
from app.core.config import settings
from app.services.upbit import UpbitApiKeyValidationError, validate_upbit_api_key

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    """사용자 계정과 Upbit API 키를 함께 등록합니다."""
    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디입니다.",
        )

    existing_access_key = db.query(ApiKey).filter(ApiKey.access_key == payload.access_key).first()
    if existing_access_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 Access Key입니다.",
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
        access_key=payload.access_key,
        secret_key=payload.secret_key,
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
