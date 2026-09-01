from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.identity.telegram_link import link_telegram_chat, unlink_telegram_chat
from app.models.user import User


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__])
    return sessionmaker(bind=engine)()


def _user(username: str, **values) -> User:
    return User(
        username=username,
        password="hashed",
        nickname=username,
        **values,
    )


def test_valid_telegram_link_code_connects_chat() -> None:
    db = _session()
    user = _user(
        "link-user",
        telegram_link_code="ABCD2345",
        telegram_link_expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(user)
    db.commit()

    assert link_telegram_chat(db, " abcd2345 ", "chat-1") is True
    db.refresh(user)
    assert user.telegram_chat_id == "chat-1"
    assert user.telegram_link_code is None
    assert user.telegram_link_expires_at is None


def test_invalid_or_expired_telegram_link_code_is_rejected() -> None:
    db = _session()
    user = _user(
        "expired-user",
        telegram_link_code="EXPR2345",
        telegram_link_expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    db.add(user)
    db.commit()

    assert link_telegram_chat(db, "WRONG234", "chat-1") is False
    assert link_telegram_chat(db, "EXPR2345", "chat-1") is False
    db.refresh(user)
    assert user.telegram_chat_id is None
    assert user.telegram_link_code == "EXPR2345"


def test_telegram_chat_already_linked_to_another_user_is_rejected() -> None:
    db = _session()
    owner = _user("owner", telegram_chat_id="shared-chat")
    candidate = _user(
        "candidate",
        telegram_link_code="LINK2345",
        telegram_link_expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add_all([owner, candidate])
    db.commit()

    assert link_telegram_chat(db, "LINK2345", "shared-chat") is False
    db.refresh(candidate)
    assert candidate.telegram_chat_id is None
    assert candidate.telegram_link_code == "LINK2345"


def test_unlink_telegram_chat_preserves_existing_behavior() -> None:
    db = _session()
    user = _user(
        "unlink-user",
        telegram_chat_id="chat-1",
        telegram_link_code="OLD23456",
        telegram_link_expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(user)
    db.commit()

    unlink_telegram_chat(db, user)
    db.refresh(user)
    assert user.telegram_chat_id is None
    assert user.telegram_link_code is None
    assert user.telegram_link_expires_at is None
