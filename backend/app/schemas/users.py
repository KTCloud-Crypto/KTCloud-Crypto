from datetime import datetime
from typing import Literal
 
from pydantic import BaseModel, ConfigDict, Field, field_validator
 
 
class UserOut(BaseModel):
    """내 프로필 조회 응답 스키마"""
 
    model_config = ConfigDict(from_attributes=True)
 
    id: int
    username: str
    nickname: str
    telegram_chat_id: str | None
    bot_enabled: bool
    execution_mode: Literal["simulated", "live"]
    live_trading_enabled: bool
    # 상단바 준비 상태 표시에 사용합니다. 키가 등록되어 있는지만 확인하며,
    # 실제 조회 가능 여부(만료·허용 IP 등)까지는 판단하지 않습니다.
    has_api_key: bool = False
 
 
class UserUpdateIn(BaseModel):
    """내 프로필 수정 요청 스키마"""
 
    nickname: str | None = Field(default=None, min_length=2, max_length=12)
    bot_enabled: bool | None = None
    execution_mode: Literal["simulated", "live"] | None = None
    live_trading_enabled: bool | None = None
 
    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not 2 <= len(normalized) <= 12:
            raise ValueError("닉네임은 공백을 제외하고 2~12자여야 합니다.")
        return normalized
 
 
class PasswordChangeIn(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=32)
    new_password: str = Field(..., min_length=8, max_length=32)
 
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("새 비밀번호는 영문과 숫자를 포함해야 합니다.")
        return value
 
 
class ExchangeKeyDeleteIn(BaseModel):
    password: str = Field(..., min_length=8, max_length=32)
 
 
class AccountStatusOut(BaseModel):
    api_key_registered: bool
    api_key_registered_at: datetime | None
    api_key_valid: bool | None = None
    api_key_status_message: str | None = None
    api_key_checked_at: datetime | None = None
 
 
class ExchangeKeyIn(BaseModel):
    """거래소 API Key 등록/갱신 요청 스키마"""
 
    access_key: str = Field(..., min_length=10, max_length=255)
    secret_key: str = Field(..., min_length=10, max_length=255)
 
 
class TelegramLinkCodeOut(BaseModel):
    code: str
    expires_at: datetime
    bot_username: str | None
