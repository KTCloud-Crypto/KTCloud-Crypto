from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SignupRequest(BaseModel):
    """회원가입 요청 스키마"""

    username: str = Field(..., min_length=4, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=32)
    nickname: str = Field(..., min_length=2, max_length=12)
    access_key: str | None = Field(default=None, min_length=10, max_length=255)
    secret_key: str | None = Field(default=None, min_length=10, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("비밀번호는 영문과 숫자를 포함해야 합니다.")
        return value

    @model_validator(mode="after")
    def validate_exchange_key_pair(self) -> "SignupRequest":
        if bool(self.access_key) != bool(self.secret_key):
            raise ValueError("Upbit Access Key와 Secret Key를 함께 입력해 주세요.")
        return self


class SignupResponse(BaseModel):
    """회원가입 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    api_key_registered_at: datetime | None = None


class LoginRequest(BaseModel):
    """로그인 요청 스키마"""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class PasswordResetRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)


class PasswordResetConfirm(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    token: str = Field(..., min_length=8, max_length=8, pattern=r"^[0-9]{8}$")
    new_password: str = Field(..., min_length=8, max_length=32)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("비밀번호는 영문과 숫자를 포함해야 합니다.")
        return value


class PasswordResetMessage(BaseModel):
    message: str


class TokenResponse(BaseModel):
    """JWT 토큰 응답 스키마"""

    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """로그인 응답 스키마"""

    id: int
    username: str
    nickname: str
    token: TokenResponse


class LoginErrorResponse(BaseModel):
    """로그인 실패 응답 스키마"""

    detail: str
    remaining_attempts: Optional[int] = None
    max_attempts: Optional[int] = None
    lockout_minutes: Optional[int] = None


class LogoutResponse(BaseModel):
    """로그아웃 응답 스키마"""

    message: str
