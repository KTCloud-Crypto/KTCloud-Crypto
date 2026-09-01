"""Identity 모듈: 사용자 인증, 거래소 연결, 보안을 담당합니다."""

from app.identity.crypto import decrypt, encrypt
from app.identity.exchange_credentials import (
    ExchangeCredentialsError,
    resolve_exchange_credentials,
)
from app.identity.security import (
    JWTError,
    LoginAttemptGuard,
    SecurityEventLogger,
    SimpleRateLimiter,
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    security_event_logger,
    verify_password,
)
from app.identity.telegram_link import (
    TelegramLinkCode,
    issue_telegram_link_code,
    link_telegram_chat,
    unlink_telegram_chat,
)

__all__ = [
    "decrypt",
    "encrypt",
    "ExchangeCredentialsError",
    "resolve_exchange_credentials",
    "JWTError",
    "LoginAttemptGuard",
    "SecurityEventLogger",
    "SimpleRateLimiter",
    "create_jwt_token",
    "decode_jwt_token",
    "hash_password",
    "security_event_logger",
    "verify_password",
    "TelegramLinkCode",
    "issue_telegram_link_code",
    "link_telegram_chat",
    "unlink_telegram_chat",
]
