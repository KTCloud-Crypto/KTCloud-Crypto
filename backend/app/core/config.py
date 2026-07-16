from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
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

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() in {"release", "production", "prod"}:
            return False
        return value

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
