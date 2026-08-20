import base64
import hashlib
import hmac
import json
import logging
import secrets
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, DefaultDict, Optional

from app.core.config import settings
from app.services.telegram import send_message


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
JWT_ALGORITHM = "HS256"
logger = logging.getLogger(__name__)


class SecurityEventLogger:
    """최근 보안 이벤트를 메모리에 저장해 관리자가 확인할 수 있게 합니다."""

    def __init__(self, max_events: int = 100) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._lock = Lock()

    def add(self, event_type: str, key: str, detail: str, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            self._events.append(
                {
                    "type": event_type,
                    "key": key,
                    "detail": detail,
                    "created_at": now.isoformat(),
                }
            )
            message = f"[Security Alert] {event_type}\nKey: {key}\nDetail: {detail}\nTime: {now.isoformat()}"
            if getattr(settings, "telegram_chat_id", ""):
                send_message(settings.telegram_chat_id, message)

    def recent(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)


security_event_logger = SecurityEventLogger()


class LoginAttemptGuard:
    """계정별 로그인 실패를 추적해 잠금 상태를 부여합니다."""

    def __init__(self, max_failures: int = 5, lockout_minutes: int = 10) -> None:
        self.max_failures = max_failures
        self.lockout_minutes = lockout_minutes
        self._failures: DefaultDict[str, list[datetime]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            attempts = self._failures.get(key, [])
            if not attempts:
                return True
            window_start = now - timedelta(minutes=self.lockout_minutes)
            recent = [attempt for attempt in attempts if attempt >= window_start]
            self._failures[key] = recent
            return len(recent) < self.max_failures

    def record_failure(self, key: str, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            attempts = self._failures.setdefault(key, [])
            attempts.append(now)
            window_start = now - timedelta(minutes=self.lockout_minutes)
            self._failures[key] = [attempt for attempt in attempts if attempt >= window_start]
            if len(self._failures[key]) >= self.max_failures:
                logger.warning("Security lockout triggered for %s after %s failures", key, len(self._failures[key]))
                security_event_logger.add(
                    "login_lockout",
                    key,
                    f"로그인 실패 {len(self._failures[key])}회로 계정 잠금",
                    now=now,
                )

    def is_locked(self, key: str, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            attempts = self._failures.get(key, [])
            if not attempts:
                return False
            window_start = now - timedelta(minutes=self.lockout_minutes)
            recent = [attempt for attempt in attempts if attempt >= window_start]
            self._failures[key] = recent
            return len(recent) >= self.max_failures

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


class SimpleRateLimiter:
    """키 기반으로 요청 수를 제한합니다."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 30) -> None:
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._requests: DefaultDict[str, list[datetime]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            requests = self._requests.setdefault(key, [])
            window_start = now - timedelta(seconds=self.window_seconds)
            requests = [request for request in requests if request >= window_start]
            if len(requests) >= self.max_requests:
                self._requests[key] = requests
                logger.warning("Security rate limit triggered for %s", key)
                security_event_logger.add(
                    "rate_limit",
                    key,
                    f"요청 제한 초과 ({self.max_requests}/{self.window_seconds}초)",
                    now=now,
                )
                return False
            requests.append(now)
            self._requests[key] = requests
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
