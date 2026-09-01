import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.messaging.notification_events import enqueue_notification_requested
from app.identity.redis_state import InMemorySecurityState, SecurityState, identity_security_state


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
JWT_ALGORITHM = "HS256"
logger = logging.getLogger(__name__)


class SecurityEventLogger:
    """최근 임시 보안 이벤트를 Identity Pod 사이에 공유합니다."""

    def __init__(self, max_events: int = 100, state: SecurityState | None = None) -> None:
        self.max_events = max_events
        self._state = state or InMemorySecurityState()

    def add(self, event_type: str, key: str, detail: str, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        self._state.add_event(
            {"type": event_type, "key": key, "detail": detail, "created_at": now.isoformat()},
            max_events=self.max_events,
        )
        message = f"[Security Alert] {event_type}\nKey: {key}\nDetail: {detail}\nTime: {now.isoformat()}"
        if getattr(settings, "telegram_chat_id", ""):
            with SessionLocal() as db:
                enqueue_notification_requested(
                    db,
                    chat_id=settings.telegram_chat_id,
                    message=message,
                    producer="identity-api",
                    notification_type="security_alert",
                )
                db.commit()

    def recent(self) -> list[dict[str, Any]]:
        return self._state.recent_events()


security_event_logger = SecurityEventLogger(state=identity_security_state)


class LoginAttemptGuard:
    """계정별 로그인 실패를 추적해 잠금 상태를 부여합니다."""

    def __init__(self, max_failures: int = 5, lockout_minutes: int = 10, state: SecurityState | None = None) -> None:
        self.max_failures = max_failures
        self.lockout_minutes = lockout_minutes
        self._state = state or InMemorySecurityState()

    def allow(self, key: str, now: Optional[datetime] = None) -> bool:
        return self.failure_count(key, now=now) < self.max_failures

    def record_failure(self, key: str, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        count = self._state.increment(
            "login-failures", key, ttl_seconds=max(1, self.lockout_minutes * 60),
            now_timestamp=now.timestamp(),
        )
        if count >= self.max_failures:
            logger.warning("Security lockout triggered for %s after %s failures", key, count)
            security_event_logger.add("login_lockout", key, f"로그인 실패 {count}회로 계정 잠금", now=now)

    def is_locked(self, key: str, now: Optional[datetime] = None) -> bool:
        return self.failure_count(key, now=now) >= self.max_failures

    def failure_count(self, key: str, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        return self._state.count("login-failures", key, now_timestamp=now.timestamp())

    def reset(self, key: str) -> None:
        self._state.reset("login-failures", key)


class SimpleRateLimiter:
    """키 기반으로 요청 수를 제한합니다."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 30, state: SecurityState | None = None, namespace: str = "rate-limit") -> None:
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._state = state or InMemorySecurityState()
        self._namespace = namespace

    def allow(self, key: str, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        count = self._state.increment(
            self._namespace, key, ttl_seconds=max(1, self.window_seconds),
            now_timestamp=now.timestamp(),
        )
        if count > self.max_requests:
            logger.warning("Security rate limit triggered for %s", key)
            security_event_logger.add(
                "rate_limit", key,
                f"요청 제한 초과 ({self.max_requests}/{self.window_seconds}초)", now=now,
            )
            return False
        return True


class JWTError(Exception):
    """JWT 생성 또는 검증 실패"""


def hash_password(password: str) -> str:
    """비밀번호를 검증 가능한 PBKDF2 해시 문자열로 변환합니다."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_digest = base64.b64encode(digest).decode("ascii")
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """저장된 PBKDF2 해시와 입력 비밀번호가 일치하는지 확인합니다."""
    try:
        algorithm, iterations, encoded_salt, encoded_digest = password_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False

        salt = base64.b64decode(encoded_salt.encode("ascii"))
        expected_digest = base64.b64decode(encoded_digest.encode("ascii"))
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual_digest, expected_digest)


def create_jwt_token(
    subject: str,
    secret_key: str,
    expires_delta: timedelta,
    token_type: str,
) -> str:
    """HS256 JWT를 생성합니다."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    signing_input = ".".join([
        _base64url_encode_json(header),
        _base64url_encode_json(payload),
    ])
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode_bytes(signature)}"


def decode_jwt_token(
    token: str,
    secret_key: str,
    expected_type: Optional[str] = None,
) -> dict[str, Any]:
    """HS256 JWT 서명, 만료 시간, 토큰 타입을 검증하고 payload를 반환합니다."""
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
        header = _base64url_decode_json(encoded_header)
        payload = _base64url_decode_json(encoded_payload)
        signature = _base64url_decode_bytes(encoded_signature)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise JWTError("유효하지 않은 토큰입니다.") from error

    if header.get("alg") != JWT_ALGORITHM or header.get("typ") != "JWT":
        raise JWTError("지원하지 않는 토큰 형식입니다.")

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise JWTError("토큰 서명이 올바르지 않습니다.")

    expires_at = payload.get("exp")
    current_timestamp = int(datetime.now(timezone.utc).timestamp())
    if not isinstance(expires_at, int) or expires_at < current_timestamp:
        raise JWTError("토큰이 만료되었습니다.")

    if expected_type is not None and payload.get("type") != expected_type:
        raise JWTError("토큰 타입이 올바르지 않습니다.")

    return payload


def _base64url_encode_json(value: dict[str, Any]) -> str:
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _base64url_encode_bytes(data)


def _base64url_encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode_json(value: str) -> dict[str, Any]:
    decoded = _base64url_decode_bytes(value).decode("utf-8")
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError("JWT payload must be an object.")
    return data


def _base64url_decode_bytes(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
