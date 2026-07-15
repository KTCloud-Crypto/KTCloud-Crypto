from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignupRequest(BaseModel):
    """회원가입 요청 스키마"""

    username: str = Field(..., min_length=4, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=32)
    nickname: str = Field(..., min_length=2, max_length=12)
    access_key: str = Field(..., min_length=10, max_length=255)
    secret_key: str = Field(..., min_length=10, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("비밀번호는 영문과 숫자를 포함해야 합니다.")
        return value


class SignupResponse(BaseModel):
    """회원가입 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    api_key_registered_at: datetime
