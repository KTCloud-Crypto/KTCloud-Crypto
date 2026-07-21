from typing import Optional

from cryptography.fernet import Fernet
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    
    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/fastapi_db"
    
    # JWT
    secret_key: str = "your-secret-key-here-change-in-production"
    access_token_expire_minutes: int = 60
    
    # API Keys
    upbit_access_key: Optional[str] = None
    upbit_secret_key: Optional[str] = None
    upbit_api_base_url: str = "https://api.upbit.com"
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # 쉼표로 구분한 허용 Origin 목록
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    # 거래소 API Key 암호화 (Fernet.generate_key()로 생성)
    master_encryption_key: str = ""

    # 텔레그램 알림 (미설정 시 알림은 조용히 무시됨)
    telegram_bot_token: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() in {"release", "production", "prod"}:
            return False
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if not self.is_production:
            return self

        if self.debug:
            raise ValueError("DEBUG must be false in production")
        if len(self.secret_key) < 32 or self.secret_key.startswith("your-secret"):
            raise ValueError("SECRET_KEY must be a random value of at least 32 characters")
        try:
            Fernet(self.master_encryption_key.encode())
        except (ValueError, TypeError) as error:
            raise ValueError("MASTER_ENCRYPTION_KEY must be a valid Fernet key") from error
        if any(origin.startswith("http://") for origin in self.cors_origin_list):
            raise ValueError("Production CORS_ORIGINS must use HTTPS")
        return self


settings = Settings()
