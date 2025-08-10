import os
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API settings
    API_STR: str = "/api"
    PROJECT_NAME: str = "CarModPicker"
    DEBUG: bool = False

    # Database settings
    DATABASE_URL: str = (
        "sqlite:///./test.db"  # will load url from env but will fallback to this if not found
    )

    # Railway-specific database URL (Railway provides this automatically)
    # This will override DATABASE_URL if present
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Any) -> str:
        # If there's a Railway DATABASE_URL in environment, use it
        railway_db_url = os.getenv("DATABASE_URL")
        if railway_db_url:
            # Railway's DATABASE_URL already includes connection parameters
            return railway_db_url
        return str(v)

    # JWT Auth
    SECRET_KEY: str = Field(...)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS settings
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://carmodpicker.webbpulse.com",
        "https://api.carmodpicker.webbpulse.com",
    ]

    # Railway deployment settings
    PORT: int = 8000
    RAILWAY_ENVIRONMENT: str = "development"

    # Email settings
    SENDGRID_API_KEY: str = Field(...)
    EMAIL_FROM: str = Field(...)
    SENDGRID_VERIFY_EMAIL_TEMPLATE_ID: str = Field(...)
    SENDGRID_RESET_PASSWORD_TEMPLATE_ID: str = Field(...)
    # Hashing settings
    HASH_ALGORITHM: str = "HS256"

    # Rate limiting settings
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings.
    For tests, this can be overridden before the first call.
    """
    return Settings(
        SECRET_KEY="test-secret-key",
        SENDGRID_API_KEY="test-sendgrid-key",
        EMAIL_FROM="test@example.com",
        SENDGRID_VERIFY_EMAIL_TEMPLATE_ID="test-verify-template",
        SENDGRID_RESET_PASSWORD_TEMPLATE_ID="test-reset-template",
    )


# Create settings instance for normal usage
settings = get_settings()
