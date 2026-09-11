"""CarModPicker's settings, layered on `webbpulse.config.BaseServiceSettings`.

`case_sensitive` is overridden because `SECRET_KEY` aliases the `SECRET_KEY_SETTING`
field and would otherwise collide with it. `_resolve_secret` resolves one at a time.
"""

import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict
from webbpulse.config import BaseServiceSettings

from app.core.secrets import fetch_app_secrets

SECRET_FIELDS = ("SECRET_KEY", "SENTRY_DSN", "EXTENSION_API_KEY")


class Settings(BaseServiceSettings):
    """Every setting CarModPicker reads, from the environment or a `.env` file."""

    API_STR: str = "/api"
    PROJECT_NAME: str = "CarModPicker"
    DEBUG: bool = False

    SECRET_KEY_SETTING: str = Field(
        default="",
        alias="SECRET_KEY",
        description="Secret key for JWT token signing. MUST be set in production!",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    EXTENSION_API_KEY_SETTING: str = Field(
        default="",
        alias="EXTENSION_API_KEY",
        description=(
            "Shared secret accepted in the X-API-Key header by ingestion routes. "
            "Empty disables API-key auth, leaving admin tokens as the only way in."
        ),
    )
    ACCESS_TOKEN_EXPIRE_MINUTES_MIN: int = 15
    ACCESS_TOKEN_EXPIRE_MINUTES_MAX: int = 10080

    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used to sign + verify JWTs. Must match on encode and decode.",
    )

    GOOGLE_CLIENT_ID: str = Field(
        default="1073035138993-bvba9dfi4pdr354p3d550bi95die8e83.apps.googleusercontent.com",
        description="Google OAuth 2.0 client id. Used as the audience when verifying ID tokens.",
    )

    @property
    def google_oauth_enabled(self) -> bool:
        """Whether a Google OAuth client id is configured."""
        return bool(self.GOOGLE_CLIENT_ID)

    FRONTEND_URL: str = Field(
        default="",
        description="Public origin of the user-facing SPA. Empty = per-environment default derived from APP_ENVIRONMENT.",
    )

    API_URL: str = Field(
        default="",
        description="Public origin of this backend API. Empty = per-environment default derived from APP_ENVIRONMENT.",
    )

    @property
    def webauthn_rp_id(self) -> str:
        """The WebAuthn relying party id: the SPA's hostname."""
        hostname = urlparse(self.FRONTEND_URL).hostname if self.FRONTEND_URL else None
        if hostname:
            return hostname
        if not self.is_production:
            return "localhost"
        if self.APP_ENVIRONMENT.lower() == "staging":
            return "staging.carmodpicker.com"
        return "carmodpicker.com"

    @property
    def webauthn_rp_name(self) -> str:
        """The WebAuthn relying party display name shown in the authenticator prompt."""
        return self.PROJECT_NAME

    @property
    def webauthn_origins_list(self) -> list[str]:
        """The origins WebAuthn assertions may come from, apex and www included."""
        if self.FRONTEND_URL:
            parsed = urlparse(self.frontend_base_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            labels = (parsed.hostname or "").split(".")
            if len(labels) == 2:
                return [origin, f"{parsed.scheme}://www.{parsed.netloc}"]
            if len(labels) == 3 and labels[0] == "www":
                return [origin, f"{parsed.scheme}://{parsed.netloc[4:]}"]
            return [origin]
        if not self.is_production:
            return ["http://localhost:4000", "http://localhost:8000"]
        if self.APP_ENVIRONMENT.lower() == "staging":
            return ["https://staging.carmodpicker.com"]
        return [
            "https://carmodpicker.com",
            "https://www.carmodpicker.com",
        ]

    @property
    def frontend_base_url(self) -> str:
        """Public origin of the SPA, for absolute links in sitemaps and email.

        From `FRONTEND_URL`, else derived from `APP_ENVIRONMENT` rather than the request
        host, since backend and frontend sit on separate domains. No trailing slash.
        """
        if self.FRONTEND_URL:
            return self.FRONTEND_URL.strip().rstrip("/")
        if not self.is_production:
            return "http://localhost:4000"
        if self.APP_ENVIRONMENT.lower() == "staging":
            return "https://staging.carmodpicker.com"
        return "https://www.carmodpicker.com"

    @property
    def api_base_url(self) -> str:
        """Public origin of this API, for links that point back at it.

        From `API_URL`, else derived from `APP_ENVIRONMENT` so staging never mails
        production links. No trailing slash.
        """
        if self.API_URL:
            return self.API_URL.strip().rstrip("/")
        if not self.is_production:
            return f"http://localhost:{self.PORT}"
        if self.APP_ENVIRONMENT.lower() == "staging":
            return "https://api.staging.carmodpicker.com"
        return "https://api.carmodpicker.com"

    @model_validator(mode="after")
    def validate_and_normalize_settings(self) -> "Settings":
        """Normalise the aliased storage and region variable names after validation.

        Deliberately never reads `SECRET_KEY`: doing so would put a Secrets Manager call
        on the import path. `require_secrets` checks it at the point of use instead.
        """
        if not self.USER_IMAGES_BUCKET and self.S3_BUCKET_NAME:
            object.__setattr__(self, "USER_IMAGES_BUCKET", self.S3_BUCKET_NAME)

        if not self.AWS_REGION or self.AWS_REGION == "auto":
            if self.AWS_DEFAULT_REGION:
                object.__setattr__(self, "AWS_REGION", self.AWS_DEFAULT_REGION)
            else:
                object.__setattr__(self, "AWS_REGION", "auto")

        if not self.S3_ENDPOINT_URL and self.AWS_ENDPOINT_URL:
            object.__setattr__(self, "S3_ENDPOINT_URL", self.AWS_ENDPOINT_URL)

        self._mirror_base_fields()
        return self

    _ENVIRONMENT_ALIASES = {
        "development": "local",
        "dev": "local",
        "local": "local",
        "test": "test",
        "testing": "test",
        "staging": "staging",
        "production": "production",
        "prod": "production",
    }

    def _mirror_base_fields(self) -> None:
        """Fill the base's lower case fields from CarModPicker's uppercase spellings.

        A pydantic field cannot be shadowed by a property, so the two are reconciled
        here rather than derived, and anything reading through the base sees the same values.
        """
        object.__setattr__(
            self,
            "environment",
            self._ENVIRONMENT_ALIASES.get(self.APP_ENVIRONMENT.strip().lower(), "local"),
        )
        object.__setattr__(self, "service_name", self.SENTRY_SERVICE_NAME or self.PROJECT_NAME)
        object.__setattr__(self, "app_secrets_arn", self.APP_SECRETS_ARN)
        object.__setattr__(self, "cors_allow_origins", self.allowed_origins_list)
        object.__setattr__(self, "cors_allow_credentials", True)

    ALLOWED_ORIGINS: str = Field(
        default=(
            "http://localhost,http://localhost:3000,http://localhost:4000,"
            "https://carmodpicker.com,"
            "https://www.carmodpicker.com,"
            "https://api.carmodpicker.com,"
            "https://staging.carmodpicker.com,"
            "https://api.staging.carmodpicker.com"
        ),
        description="Comma-separated list of allowed origins",
    )

    CHROME_EXTENSION_IDS: str = Field(
        default="dbglgmnnfandmnacdpibkfggkadjikkg",
        description=(
            "Comma-separated Chrome extension ids allowed as CORS origins. Each becomes a "
            "chrome-extension://<id> entry. Set to add an unpacked development id."
        ),
    )

    @property
    def chrome_extension_origins_list(self) -> list[str]:
        """The `chrome-extension://<id>` CORS origins from `CHROME_EXTENSION_IDS`.

        An explicit list, never a wildcard pattern: with `allow_credentials=True` a
        pattern would let any installed extension read authenticated responses.
        """
        ids = [value.strip() for value in self.CHROME_EXTENSION_IDS.split(",") if value.strip()]
        origins: list[str] = []
        for extension_id in ids:
            origin = (
                extension_id if extension_id.startswith("chrome-extension://") else f"chrome-extension://{extension_id}"
            )
            if origin not in origins:
                origins.append(origin)
        return origins

    @property
    def allowed_origins_list(self) -> list[str]:
        """Every origin CORS admits: `ALLOWED_ORIGINS` plus the extension origins.

        The literal `"null"` origin is excluded on purpose, since sandboxed iframes and
        `file://` pages send it and would otherwise get credentialed access.
        """
        origins = []
        if self.ALLOWED_ORIGINS:
            origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

        for origin in self.chrome_extension_origins_list:
            if origin not in origins:
                origins.append(origin)

        return origins

    PORT: int = 8000
    APP_ENVIRONMENT: str = "development"
    RUN_STARTUP_TASKS: bool = Field(
        default=True,
        description="Run lifespan startup work (car generation seed, orphan job sweep). Lambda sets this false.",
    )

    IDENTITY_ISSUER: str = Field(
        default="",
        description=(
            "The identity issuer, as terraform/identity.tf renders it. Empty means the "
            "webbpulse.identity router does not mount, which is the state of a local run "
            "and of the test suite. Set on the deployed identity function only."
        ),
    )

    DYNAMODB_TABLE_PREFIX: str = Field(
        default="",
        description="Prefix for every DynamoDB table name. Empty = carmodpicker-<APP_ENVIRONMENT>.",
    )
    DYNAMODB_ENDPOINT_URL: str = Field(
        default="",
        description="DynamoDB endpoint override (DynamoDB Local). Empty = native AWS endpoint.",
    )
    DYNAMODB_SEARCH_SCAN_PAGE_LIMIT: int = Field(
        default=50,
        description="Maximum number of DynamoDB scan pages a single catalog search may read before it stops.",
    )

    @property
    def dynamodb_table_prefix(self) -> str:
        """The DynamoDB table name prefix, defaulting to `carmodpicker-<environment>`."""
        return self.DYNAMODB_TABLE_PREFIX or f"carmodpicker-{self.APP_ENVIRONMENT.lower()}"

    @property
    def is_production(self) -> bool:
        """True outside debug mode and the development environment."""
        return not self.DEBUG and self.APP_ENVIRONMENT.lower() != "development"

    @property
    def secure_cookies(self) -> bool:
        """Whether cookies should carry the Secure flag (HTTPS only)."""
        return self.is_production

    EMAIL_ENABLED: bool = Field(
        default=False,
        description=(
            "Enable email sending via SES. Set to true in production. " "When false, email calls are silently skipped."
        ),
    )
    EMAIL_FROM: str = Field(default="")

    SENTRY_DSN_SETTING: str = Field(
        default="",
        alias="SENTRY_DSN",
        description="Sentry DSN for error reporting. Empty = Sentry disabled. Injected via Secrets Manager in prod (D-01, D-55).",
    )
    SENTRY_RELEASE: str = Field(
        default="",
        description="Release identifier baked at Docker build time (typically git commit SHA, set by GitHub Actions per D-02).",
    )
    SENTRY_SERVICE_NAME: str = Field(
        default="",
        description="Per-process server_name tag: 'apprunner-backend', 'ecs-crawler', 'crawler-cli' (D-11).",
    )

    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000

    RATE_LIMIT_GET_REQUESTS_PER_MINUTE: int = 200
    RATE_LIMIT_GET_REQUESTS_PER_HOUR: int = 20000
    RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE: int = 10
    RATE_LIMIT_AUTH_REQUESTS_PER_HOUR: int = 100
    RATE_LIMIT_ADMIN_REQUESTS_PER_MINUTE: int = 30
    RATE_LIMIT_ADMIN_REQUESTS_PER_HOUR: int = 300

    ENABLE_SHARED_RATE_LIMITING: bool = True
    RATE_LIMITS_TABLE: str = ""

    USER_IMAGES_BUCKET: str = Field(
        default="",
        description="S3 bucket name for user image uploads. Also accepts S3_BUCKET_NAME.",
    )
    CRAWLED_PAGE_MAX_HTML_BYTES: int = Field(
        default=8 * 1024 * 1024,
        description="Maximum UTF-8 size in bytes for extension-submitted page HTML.",
    )
    S3_BUCKET_NAME: str = Field(
        default="",
        description="Alternative name for USER_IMAGES_BUCKET (maps to USER_IMAGES_BUCKET if not set)",
    )
    AWS_ACCESS_KEY_ID: str = Field(
        default="",
        description="AWS access key ID. Leave empty on App Runner to use the instance IAM role.",
    )
    AWS_SECRET_ACCESS_KEY: str = Field(
        default="",
        description="AWS secret access key. Leave empty on App Runner to use the instance IAM role.",
    )
    AWS_SESSION_TOKEN: str = Field(
        default="",
        description="AWS session token. Lambda sets this alongside the key pair; required whenever the credentials are temporary.",
    )
    AWS_REGION: str = Field(
        default="auto",
        description="AWS region for the S3 bucket. Also accepts AWS_DEFAULT_REGION.",
    )
    AWS_DEFAULT_REGION: str = Field(
        default="",
        description="Alternative name for region (maps to AWS_REGION if AWS_REGION is not set)",
    )
    S3_ENDPOINT_URL: str = Field(
        default="",
        description="S3 endpoint URL. Leave empty for native AWS S3.",
    )
    AWS_ENDPOINT_URL: str = Field(
        default="",
        description="Alternative name for endpoint URL (maps to S3_ENDPOINT_URL if S3_ENDPOINT_URL is not set)",
    )
    MAX_IMAGE_SIZE_MB: int = Field(default=10, description="Maximum image file size in MB")
    ALLOWED_IMAGE_EXTENSIONS: str = Field(
        default="jpg,jpeg,png,gif,webp",
        description="Comma-separated list of allowed image file extensions",
    )
    PRESIGNED_URL_EXPIRATION: int = Field(
        default=86400,
        description="Presigned URL expiration time in seconds (default: 24 hours)",
    )

    @property
    def allowed_image_extensions_list(self) -> list[str]:
        """The allowed image file extensions, lowercased."""
        if not self.ALLOWED_IMAGE_EXTENSIONS:
            return []
        return [ext.strip().lower() for ext in self.ALLOWED_IMAGE_EXTENSIONS.split(",") if ext.strip()]

    @property
    def max_image_size_bytes(self) -> int:
        """The maximum upload image size, in bytes."""
        return self.MAX_IMAGE_SIZE_MB * 1024 * 1024

    APP_SECRETS_ARN: str = Field(
        default="",
        description=(
            "ARN of the one JSON secret holding SECRET_FIELDS. Empty = secrets come "
            "from the environment only and no Secrets Manager call is ever made."
        ),
    )

    def _resolve_secret(self, name: str) -> str:
        """Resolve one secret, preferring the environment over the `APP_SECRETS_ARN` blob.

        Returns an empty string when neither supplies it.
        """
        from_env = os.environ.get(name, "") or getattr(self, f"{name}_SETTING", "")
        if from_env:
            return from_env
        arn = os.environ.get("APP_SECRETS_ARN", "") or self.APP_SECRETS_ARN
        if not arn:
            return ""
        return fetch_app_secrets(arn).get(name, "")

    @property
    def SECRET_KEY(self) -> str:
        """The JWT signing key, resolved on access."""
        return self._resolve_secret("SECRET_KEY")

    @property
    def SENTRY_DSN(self) -> str:
        """The Sentry DSN, resolved on access. Empty disables Sentry."""
        return self._resolve_secret("SENTRY_DSN")

    @property
    def EXTENSION_API_KEY(self) -> str:
        """The shared X-API-Key secret for ingestion routes, resolved on access."""
        return self._resolve_secret("EXTENSION_API_KEY")

    def require_secrets(self, *names: str) -> None:
        """Raise unless every named secret resolves to a non-empty value.

        Called at the point of use rather than at import, so a read-only domain that
        never signs a token needs neither the secret nor the IAM grant.
        """
        unknown = [name for name in names if name not in SECRET_FIELDS]
        if unknown:
            raise ValueError(f"Unknown secret(s): {', '.join(sorted(unknown))}")
        missing = [name for name in names if not self._resolve_secret(name)]
        if missing:
            raise ValueError(
                "Missing required secret(s) (set them as environment variables or "
                f"as keys of the APP_SECRETS_ARN secret): {', '.join(missing)}"
            )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """The process-wide `Settings`, cached so the env is parsed once.

    Tests may override it before the first call.
    """
    return Settings()


settings = get_settings()
