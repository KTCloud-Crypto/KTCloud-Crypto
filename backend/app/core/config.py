from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수와 로컬 .env를 애플리케이션 설정으로 변환합니다."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/fastapi_db"

    # JWT
    secret_key: str = "your-secret-key-here-change-in-production"
    access_token_expire_minutes: int = 60

    # Security
    login_max_failures: int = 5
    login_lockout_minutes: int = 10
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 30
    sensitive_endpoint_rate_limit_window_seconds: int = 60
    sensitive_endpoint_rate_limit_max_requests: int = 10

    # Upbit
    upbit_api_base_url: str = "https://api.upbit.com"
    upbit_ws_url: str = "wss://api.upbit.com/websocket/v1"
    watch_markets: str = "KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-DOGE,KRW-TRX"
    strategy_refresh_seconds: int = 30

    # Environment
    environment: str = "development"

    # 쉼표로 구분한 허용 Origin 목록
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost,http://localhost:80,http://127.0.0.1,http://127.0.0.1:80"
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
    telegram_bot_username: str = ""
    telegram_chat_id: str = ""
    position_reconciliation_seconds: int = 60
    stale_execution_seconds: int = 120

    @property
    def watch_market_list(self) -> list[str]:
        return [market.strip().upper() for market in self.watch_markets.split(",") if market.strip()]


settings = Settings()
