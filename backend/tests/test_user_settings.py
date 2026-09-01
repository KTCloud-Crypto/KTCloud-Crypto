from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from fastapi import HTTPException

from app.identity.api_users import (
    account_status,
    create_telegram_link_code,
    delete_exchange_key,
    read_telegram_link_code,
    update_me,
)
from app.schemas.users import PasswordChangeIn, UserUpdateIn


def test_profile_update_trims_nickname() -> None:
    payload = UserUpdateIn(nickname="  영진  ")

    assert payload.nickname == "영진"


def test_profile_update_response_keeps_api_key_readiness() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (1,)
    user = SimpleNamespace(
        id=1,
        username="tester",
        nickname="테스터",
        telegram_chat_id="1234",
        bot_enabled=True,
        execution_mode="simulated",
        live_trading_enabled=False,
    )

    result = update_me(UserUpdateIn(execution_mode="live"), db=db, current_user=user)

    assert result.execution_mode == "live"
    assert result.has_api_key is True


def test_live_mode_requires_api_key() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    user = SimpleNamespace(
        id=1,
        username="tester",
        nickname="테스터",
        telegram_chat_id=None,
        bot_enabled=True,
        execution_mode="simulated",
        live_trading_enabled=False,
    )

    with pytest.raises(HTTPException) as caught:
        update_me(UserUpdateIn(execution_mode="live"), db=db, current_user=user)

    assert caught.value.status_code == 409


def test_deleting_exchange_key_keeps_paper_trading_enabled() -> None:
    db = MagicMock()
    user = SimpleNamespace(
        id=1,
        password="hashed",
        bot_enabled=True,
        execution_mode="live",
        live_trading_enabled=True,
    )

    with (
        patch("app.identity.api_users.sensitive_action_limiter.allow", return_value=True),
        patch("app.identity.api_users.verify_password", return_value=True),
        patch("app.identity.api_users.disable_live_subscriptions") as disable_live,
        patch("app.identity.api_users.record_security_event"),
    ):
        delete_exchange_key(
            SimpleNamespace(password="Password123"),
            request=None,
            db=db,
            current_user=user,
        )

    assert user.bot_enabled is True
    assert user.live_trading_enabled is False
    assert user.execution_mode == "simulated"
    disable_live.assert_called_once_with(1)


def test_account_status_validates_registered_api_key() -> None:
    created_at = datetime.utcnow()
    api_key = SimpleNamespace(
        encrypted_access_key="encrypted-access",
        encrypted_secret_key="encrypted-secret",
        created_at=created_at,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = api_key
    user = SimpleNamespace(id=1)

    with (
        patch(
            "app.identity.api_users.resolve_exchange_credentials",
            return_value=("access", "secret"),
        ) as resolve_credentials,
        patch("app.identity.api_users.validate_upbit_api_key") as validate_key,
    ):
        validate_key.return_value = SimpleNamespace(is_valid=True, message="정상")

        result = account_status(db=db, current_user=user)

    resolve_credentials.assert_called_once_with(api_key)
    assert result.api_key_registered is True
    assert result.api_key_registered_at == created_at
    assert result.api_key_valid is True
    assert result.api_key_status_message == "정상"


@pytest.mark.parametrize("nickname", [" ", " 이름이열세글자를넘어갑니다 "])
def test_profile_update_rejects_invalid_trimmed_nickname(nickname: str) -> None:
    with pytest.raises(ValidationError):
        UserUpdateIn(nickname=nickname)


@pytest.mark.parametrize("new_password", ["onlyletters", "12345678"])
def test_password_change_requires_letters_and_numbers(new_password: str) -> None:
    with pytest.raises(ValidationError):
        PasswordChangeIn(current_password="Oldpass123", new_password=new_password)


def test_password_change_accepts_strong_password() -> None:
    payload = PasswordChangeIn(current_password="Oldpass123", new_password="Newpass456")

    assert payload.new_password == "Newpass456"


def test_telegram_link_code_can_be_restored_after_page_reload() -> None:
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    user = SimpleNamespace(telegram_link_code="123456", telegram_link_expires_at=expires_at)

    result = read_telegram_link_code(current_user=user)

    assert result is not None
    assert result.code == "123456"
    assert result.expires_at == expires_at


def test_telegram_link_code_is_alphanumeric_and_expires_in_ten_minutes() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    user = SimpleNamespace(
        telegram_chat_id="old-chat",
        telegram_link_code=None,
        telegram_link_expires_at=None,
    )
    before = datetime.utcnow()

    with patch("app.identity.api_users.settings.telegram_bot_token", "test-token"):
        result = create_telegram_link_code(db=db, current_user=user)

    assert len(result.code) == 8
    assert result.code.isalnum()
    assert any(character.isalpha() for character in result.code)
    assert any(character.isdigit() for character in result.code)
    assert before + timedelta(minutes=9, seconds=55) <= result.expires_at
    assert result.expires_at <= datetime.utcnow() + timedelta(minutes=10)
    assert user.telegram_chat_id is None
    db.commit.assert_called_once()


def test_telegram_link_code_returns_none_before_issue() -> None:
    user = SimpleNamespace(telegram_link_code=None, telegram_link_expires_at=None)

    assert read_telegram_link_code(current_user=user) is None
