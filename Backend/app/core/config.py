from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # API settings
    API_STR: str = "/api"
    PROJECT_NAME: str = "CarModPicker"
    DEBUG: bool = True

    # Database settings
    DATABASE_URL: str = (
        "sqlite:///./test.db"  # will load url from env but will fallback to this if not found
    )

    # JWT Auth
    SECRET_KEY: str = Field(...)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS settings
    ALLOWED_ORIGINS: list[str] = ["http://localhost"]

    # Email settings
    SENDGRID_API_KEY: str
    EMAIL_FROM: str
    SENDGRID_VERIFY_EMAIL_TEMPLATE_ID: str
    SENDGRID_RESET_PASSWORD_TEMPLATE_ID: str
    # Hashing settings
    HASH_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache()
def get_settings():
    """
    Get cached settings.
    For tests, this can be overridden before the first call.
    """
    return Settings()


# Create settings instance for normal usage
settings = get_settings()
