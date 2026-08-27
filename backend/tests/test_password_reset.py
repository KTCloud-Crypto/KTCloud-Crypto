import re
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import confirm_password_reset, request_password_reset
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import PasswordResetConfirm, PasswordResetRequest
from app.identity import hash_password, verify_password


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_password_reset_token_is_hashed_and_single_use(db) -> None:
    user = User(
        username="reset_user",
        password=hash_password("Oldpass123"),
        nickname="reset",
        telegram_chat_id="123456",
    )
    db.add(user)
    db.commit()

    with patch.object(settings, "telegram_bot_token", "test-token"), patch(
        "app.api.auth.send_message", return_value=True
    ) as send:
        request_password_reset(PasswordResetRequest(username=user.username), db)
        message = send.call_args.args[1]
        token = re.search(r"인증 코드: ([0-9]{8})", message).group(1)

        assert user.password_reset_token_hash
        assert token not in user.password_reset_token_hash

        result = confirm_password_reset(
            PasswordResetConfirm(username=user.username, token=token, new_password="Newpass456"),
            db,
        )

    assert "변경" in result.message
    assert verify_password("Newpass456", user.password)
    assert user.password_reset_token_hash is None

    with pytest.raises(HTTPException) as error:
        confirm_password_reset(
            PasswordResetConfirm(username=user.username, token=token, new_password="Other789pass"),
            db,
        )
    assert error.value.status_code == 400


def test_password_reset_request_does_not_reveal_unknown_account(db) -> None:
    with patch.object(settings, "telegram_bot_token", "test-token"), patch(
        "app.api.auth.send_message"
    ) as send:
        result = request_password_reset(PasswordResetRequest(username="unknown_user"), db)

    assert "전송" in result.message
    send.assert_not_called()
