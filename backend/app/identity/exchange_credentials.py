from app.models.api_key import ApiKey
from app.identity.crypto import decrypt


class ExchangeCredentialsError(ValueError):
    """저장된 거래소 인증 정보를 사용할 수 없을 때 발생합니다."""


def resolve_exchange_credentials(api_key: ApiKey | None) -> tuple[str, str]:
    """DB에 암호화해 저장한 Upbit 키를 복호화합니다."""
    if api_key is None:
        raise ExchangeCredentialsError("Upbit API 키가 등록되지 않았습니다.")

    if api_key.encrypted_access_key and api_key.encrypted_secret_key:
        try:
            return (
                decrypt(api_key.encrypted_access_key),
                decrypt(api_key.encrypted_secret_key),
            )
        except Exception as error:
            raise ExchangeCredentialsError(
                "Upbit API 키를 복호화할 수 없습니다. 키를 다시 등록해 주세요."
            ) from error

    raise ExchangeCredentialsError("암호화된 Upbit API 키를 다시 등록해 주세요.")
