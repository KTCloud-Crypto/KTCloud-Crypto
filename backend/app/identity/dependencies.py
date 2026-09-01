from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import user_id_var
from app.identity import JWTError, decode_jwt_token
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """공유 JWT 검증으로 현재 사용자를 확인합니다.

    각 API runtime은 동일한 서명 키로 토큰을 로컬 검증하므로 Identity API를
    매 요청마다 호출하지 않습니다. shared RDS 단계에서는 사용자 존재 여부만
    로컬 session에서 확인합니다.
    """
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
