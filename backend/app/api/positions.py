from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.position import Position
from app.models.user import User
from app.schemas.positions import PositionOut, UpbitBalanceOut
from app.services.crypto import decrypt
from app.services.upbit import UpbitApiKeyValidationError, get_accounts

router = APIRouter(
    prefix="/positions",
    tags=["Positions"],
)


def get_api_key_credentials(api_key: ApiKey) -> tuple[str, str]:
    """저장된 암호화 컬럼에서 Upbit 인증 정보를 복호화합니다."""
    if api_key.encrypted_access_key and api_key.encrypted_secret_key:
        try:
            return (
                decrypt(api_key.encrypted_access_key),
                decrypt(api_key.encrypted_secret_key),
            )
        except (InvalidToken, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="서버 암호화 키 설정을 확인해 주세요.",
            ) from error

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="등록된 Upbit API Key가 없습니다.",
    )


@router.get("", response_model=list[PositionOut])
def list_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Position]:
    """DB에 기록된 내 포지션 목록을 조회합니다 (웹훅 매매 결과 기준)."""
    return (
        db.query(Position)
        .filter(Position.user_id == current_user.id)
        .order_by(Position.updated_at.desc())
        .all()
    )


@router.get("/balance", response_model=list[UpbitBalanceOut])
def get_upbit_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UpbitBalanceOut]:
    """등록된 Upbit API Key로 실제 계좌 잔고를 실시간 조회합니다."""
    api_key = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).first()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="등록된 Upbit API Key가 없습니다.",
        )

    try:
        access_key, secret_key = get_api_key_credentials(api_key)
        accounts = get_accounts(
            access_key=access_key,
            secret_key=secret_key,
            base_url=settings.upbit_api_base_url,
        )
    except UpbitApiKeyValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        )

    return [
        UpbitBalanceOut(
            currency=account["currency"],
            balance=float(account["balance"]),
            locked=float(account["locked"]),
            avg_buy_price=float(account["avg_buy_price"]),
        )
        for account in accounts
    ]
