from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import os


# Get the project root directory (parent of app/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Debug: Print the .env file path and check if it exists
print(f"[CONFIG] Looking for .env file at: {ENV_FILE}")
print(f"[CONFIG] .env file exists: {ENV_FILE.exists()}")


class Settings(BaseSettings):
    """Application configuration settings."""
    
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/sendinchat_db"
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Third-Party Wallet API
    WALLET_API_BASE_URL: str = "http://102.216.128.75:9090/waas/api/v1"
    WALLET_AUTH_API_BASE_URL: str = ""
    WALLET_API_USERNAME: str = ""
    WALLET_API_PASSWORD: str = ""
    WALLET_API_CLIENT_ID: str = ""
    WALLET_API_CLIENT_SECRET: str = ""
    WALLET_API_TIMEOUT: int = 30
    
    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = 'utf-8'
        case_sensitive = True


settings = Settings()

# Debug: Print loaded settings (mask sensitive data)
print(f"[CONFIG] Loaded DATABASE_URL: {settings.DATABASE_URL[:30]}...")
print(f"[CONFIG] Loaded SECRET_KEY: {settings.SECRET_KEY[:20]}...")
print(f"[CONFIG] Loaded ALGORITHM: {settings.ALGORITHM}")
print(f"[CONFIG] Loaded ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
