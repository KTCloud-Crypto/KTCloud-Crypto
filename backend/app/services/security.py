import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
JWT_ALGORITHM = "HS256"


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
    expected_type: str | None = None,
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
