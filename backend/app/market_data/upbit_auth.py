import base64
import hashlib
import hmac
import json
import uuid
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from app.core.metrics import EXTERNAL_DURATION, EXTERNAL_REQUESTS


def _observe(operation: str, started: float, outcome: str) -> None:
    EXTERNAL_DURATION.labels("upbit", operation).observe(time.perf_counter() - started)
    EXTERNAL_REQUESTS.labels("upbit", operation, outcome).inc()


class UpbitApiKeyValidationError(Exception):
    """Upbit API 키 검증 실패"""


@dataclass
class UpbitValidationResult:
    is_valid: bool
    message: str


def validate_upbit_api_key(
    access_key: str,
    secret_key: str,
    base_url: str,
    timeout: float = 5.0,
) -> UpbitValidationResult:
    """Upbit 개인 API 호출로 Access Key와 Secret Key가 실제 유효한지 확인합니다."""
    token = _create_jwt(access_key, secret_key)
    request = Request(
        f"{base_url.rstrip('/')}/v1/accounts",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )

    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            _observe("validate_api_key", started, "success" if response.status == 200 else "error")
            if response.status == 200:
                return UpbitValidationResult(is_valid=True, message="유효한 Upbit API Key입니다.")
            return UpbitValidationResult(
                is_valid=False,
                message="Upbit API Key를 확인할 수 없습니다.",
            )
    except HTTPError as error:
        _observe("validate_api_key", started, "rate_limited" if error.code == 429 else "http_error")
        return UpbitValidationResult(is_valid=False, message=_message_from_http_error(error))
    except URLError as error:
        _observe("validate_api_key", started, "connection_error")
        raise UpbitApiKeyValidationError("Upbit API 서버에 연결할 수 없습니다.") from error
    except TimeoutError as error:
        _observe("validate_api_key", started, "timeout")
        raise UpbitApiKeyValidationError("Upbit API 서버 응답 시간이 초과되었습니다.") from error


def get_accounts(
    access_key: str,
    secret_key: str,
    base_url: str,
    timeout: float = 5.0,
) -> list[dict]:
    """Upbit 개인 계좌의 보유 잔고 목록을 조회합니다."""
    token = _create_jwt(access_key, secret_key)
    request = Request(
        f"{base_url.rstrip('/')}/v1/accounts",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )

    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
            _observe("get_accounts", started, "success")
            return result
    except HTTPError as error:
        _observe("get_accounts", started, "rate_limited" if error.code == 429 else "http_error")
        raise UpbitApiKeyValidationError(_message_from_http_error(error)) from error
    except URLError as error:
        _observe("get_accounts", started, "connection_error")
        raise UpbitApiKeyValidationError("Upbit API 서버에 연결할 수 없습니다.") from error
    except TimeoutError as error:
        _observe("get_accounts", started, "timeout")
        raise UpbitApiKeyValidationError("Upbit API 서버 응답 시간이 초과되었습니다.") from error


def _create_jwt(access_key: str, secret_key: str) -> str:
    header = {"alg": "HS512", "typ": "JWT"}
    payload = {"access_key": access_key, "nonce": str(uuid.uuid4())}

    signing_input = ".".join([
        _base64url_encode(header),
        _base64url_encode(payload),
    ])
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha512,
    ).digest()

    return f"{signing_input}.{_base64url_encode_bytes(signature)}"


def _base64url_encode(value: dict[str, str]) -> str:
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _base64url_encode_bytes(data)


def _base64url_encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _message_from_http_error(error: HTTPError) -> str:
    if error.code == 401:
        return "Upbit Access Key 또는 Secret Key가 올바르지 않습니다."
    if error.code == 403:
        return "Upbit API Key 권한 또는 허용 IP 설정을 확인해 주세요."
    if error.code == 429:
        return "Upbit API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
    return "Upbit API Key 검증에 실패했습니다."
