import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
 
 
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
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status == 200:
                return UpbitValidationResult(is_valid=True, message="유효한 Upbit API Key입니다.")
            return UpbitValidationResult(
                is_valid=False,
                message="Upbit API Key를 확인할 수 없습니다.",
            )
    except HTTPError as error:
        return UpbitValidationResult(is_valid=False, message=_message_from_http_error(error))
    except URLError as error:
        raise UpbitApiKeyValidationError("Upbit API 서버에 연결할 수 없습니다.") from error
    except TimeoutError as error:
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
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except HTTPError as error:
        raise UpbitApiKeyValidationError(_message_from_http_error(error))from error
    except URLError as error:
        raise UpbitApiKeyValidationError("Upbit API 서버에 연결할 수 없습니다.") from error
    except TimeoutError as error:
        raise UpbitApiKeyValidationError("Upbit API 서버 응답 시간이 초과되었습니다.") from error
 
 
async def get_accounts_async(
    access_key: str,
    secret_key: str,
    base_url: str,
    timeout: float = 5.0,
) -> list[dict]:
    """동기 get_accounts를 이벤트 루프 밖에서 실행합니다.
 
    urllib 기반 동기 호출이라 async 요청 경로에서 직접 부르면 이벤트 루프가
    멈춰 다른 요청까지 함께 지연됩니다. upbit_service.get_current_price와
    동일하게 executor로 넘겨 처리합니다.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: get_accounts(
            access_key=access_key,
            secret_key=secret_key,
            base_url=base_url,
            timeout=timeout,
        ),
    )
 
 
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
 