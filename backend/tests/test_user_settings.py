import pytest
from pydantic import ValidationError

from app.schemas.users import PasswordChangeIn, UserUpdateIn


def test_profile_update_trims_nickname() -> None:
    payload = UserUpdateIn(nickname="  영진  ")

    assert payload.nickname == "영진"


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
