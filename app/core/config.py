"""
Application settings loaded from environment variables and optional .env file.
"""
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (sendinchat-server/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/sendinchat_db"
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 9PSB WAAS wallet API
    WALLET_API_BASE_URL: str = "http://102.216.128.75:9090/waas/api/v1"
    WALLET_AUTH_API_BASE_URL: str = ""
    WALLET_API_USERNAME: str = ""
    WALLET_API_PASSWORD: str = ""
    WALLET_API_CLIENT_ID: str = ""
    WALLET_API_CLIENT_SECRET: str = ""
    WALLET_API_TIMEOUT: int = 30
    WALLET_MERCHANT_SHORT_CODE: str = ""

    # Incoming wallet-provider webhook Basic Auth (share with third-party provider)
    WEBHOOK_USERNAME: str = ""
    WEBHOOK_PASSWORD: str = ""

    @model_validator(mode="after")
    def default_wallet_auth_url(self) -> "Settings":
        if not self.WALLET_AUTH_API_BASE_URL.strip():
            self.WALLET_AUTH_API_BASE_URL = self.WALLET_API_BASE_URL
        return self


settings = Settings()
