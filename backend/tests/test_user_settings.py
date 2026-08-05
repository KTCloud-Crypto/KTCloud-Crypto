from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.api.users import account_status, read_telegram_link_code, update_me
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
            "app.api.users.resolve_exchange_credentials",
            return_value=("access", "secret"),
        ) as resolve_credentials,
        patch("app.api.users.validate_upbit_api_key") as validate_key,
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


def test_telegram_link_code_returns_none_before_issue() -> None:
    user = SimpleNamespace(telegram_link_code=None, telegram_link_expires_at=None)

    assert read_telegram_link_code(current_user=user) is None
