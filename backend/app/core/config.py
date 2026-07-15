from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/fastapi_db"
    
    # JWT
    secret_key: str = "your-secret-key-here-change-in-production"
    
    # API Keys
    upbit_access_key: Optional[str] = None
    upbit_secret_key: Optional[str] = None
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
