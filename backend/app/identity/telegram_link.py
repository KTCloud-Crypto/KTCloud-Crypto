from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.user import User


@dataclass(frozen=True, slots=True)
class TelegramLinkCode:
    code: str
    expires_at: datetime


def issue_telegram_link_code(
    db: Session,
    user: User,
    *,
    now: datetime | None = None,
) -> TelegramLinkCode:
    """기존 연결을 해제하고 10분 동안 유효한 일회용 코드를 발급합니다."""
    issued_at = now or datetime.utcnow()
    expires_at = issued_at + timedelta(minutes=10)
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    alphabet = letters + digits

    for _ in range(10):
        characters = [secrets.choice(letters), secrets.choice(digits)]
        characters.extend(secrets.choice(alphabet) for _ in range(6))
        secrets.SystemRandom().shuffle(characters)
        code = "".join(characters)
        exists = db.query(User.id).filter(User.telegram_link_code == code).first()
        if exists is None:
            break
    else:
        raise RuntimeError("텔레그램 연동 코드를 생성할 수 없습니다.")

    user.telegram_chat_id = None
    user.telegram_link_code = code
    user.telegram_link_expires_at = expires_at
    db.commit()
    return TelegramLinkCode(code=code, expires_at=expires_at)


def link_telegram_chat(
    db: Session,
    code: str,
    chat_id: str,
    *,
    now: datetime | None = None,
) -> bool:
    """유효한 일회용 코드와 아직 사용되지 않은 Telegram chat을 연결합니다."""
    normalized_code = code.strip().upper()
    current_time = now or datetime.utcnow()
    user = (
        db.query(User)
        .filter(
            User.telegram_link_code == normalized_code,
            User.telegram_link_expires_at >= current_time,
        )
        .first()
    )
    if user is None:
        return False

    chat_owner = db.query(User.id).filter(User.telegram_chat_id == chat_id).first()
    if chat_owner is not None and chat_owner[0] != user.id:
        return False

    user.telegram_chat_id = chat_id
    user.telegram_link_code = None
    user.telegram_link_expires_at = None
    db.commit()
    return True


def unlink_telegram_chat(db: Session, user: User) -> None:
    """사용자의 Telegram 연결과 남아 있는 일회용 코드를 제거합니다."""
    user.telegram_chat_id = None
    user.telegram_link_code = None
    user.telegram_link_expires_at = None
    db.commit()
