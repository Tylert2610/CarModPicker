import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.secrets import fetch_app_secrets

# Settings whose value may come from the single JSON secret named by
# APP_SECRETS_ARN. Its keys are these names exactly, so there is no mapping to
# keep in step. Each is stored in a shadow field and exposed as a property that
# resolves on first read, so importing this module performs no network call and
# a process that never reads a secret never needs secretsmanager:GetSecretValue.
SECRET_FIELDS = ("SECRET_KEY", "SENTRY_DSN")


class Settings(BaseSettings):
    # API settings
    API_STR: str = "/api"
    PROJECT_NAME: str = "CarModPicker"
    DEBUG: bool = False

    # JWT Auth. Resolved lazily through the SECRET_KEY property below; an
    # environment variable still wins, which keeps local development and the
    # test suite free of AWS.
    SECRET_KEY_SETTING: str = Field(
        default="",
        alias="SECRET_KEY",
        description="Secret key for JWT token signing. MUST be set in production!",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Bounds for user-configurable session length (minutes). User preference is clamped to this range.
    ACCESS_TOKEN_EXPIRE_MINUTES_MIN: int = 15
    ACCESS_TOKEN_EXPIRE_MINUTES_MAX: int = 10080  # 7 days

    # JWT algorithm — PyJWT swap (AUTH-04 D-03). HS256 preserved per D-46.
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used to sign + verify JWTs. Must match on encode and decode.",
    )

    # Google OAuth — frontend uses this client id to mint ID tokens; backend uses it as the
    # `audience` when verifying. The client id itself is not a secret (it's embedded in the
    # frontend bundle anyway), so it lives in source. Override via env if/when rotated.
    GOOGLE_CLIENT_ID: str = Field(
        default="1073035138993-bvba9dfi4pdr354p3d550bi95die8e83.apps.googleusercontent.com",
        description="Google OAuth 2.0 client id. Used as the audience when verifying ID tokens.",
    )

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID)

    FRONTEND_URL: str = Field(
        default="",
        description="Public origin of the user-facing SPA. Empty = per-environment default derived from APP_ENVIRONMENT.",
    )

    # WebAuthn / passkeys — RP ID and origins are derived from FRONTEND_URL when
    # it is set, otherwise from APP_ENVIRONMENT.
    # RP ID is the registrable domain users see; origins are the frontend URLs
    # that will call navigator.credentials.*. Passkeys registered on one
    # environment cannot be used on another (different RP IDs).
    @property
    def webauthn_rp_id(self) -> str:
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
        return self.PROJECT_NAME

    @property
    def webauthn_origins_list(self) -> list[str]:
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
        """Public origin of the user-facing SPA, used to build absolute URLs
        (e.g. sitemap <loc> entries, email links). The backend and frontend
        live on separate domains, so this comes from FRONTEND_URL when set and
        otherwise from APP_ENVIRONMENT rather than the request host. No
        trailing slash."""
        if self.FRONTEND_URL:
            return self.FRONTEND_URL.strip().rstrip("/")
        if not self.is_production:
            return "http://localhost:4000"
        if self.APP_ENVIRONMENT.lower() == "staging":
            return "https://staging.carmodpicker.com"
        return "https://www.carmodpicker.com"

    @model_validator(mode="after")
    def validate_and_normalize_settings(self) -> "Settings":
        """Normalize storage variable names.

        Deliberately does not look at SECRET_KEY. Reading it here would resolve
        the secret at construction time and put a Secrets Manager call back on
        the import path, which is exactly what this module no longer does. The
        production check moved to require_secrets(), called at the point of use.
        """
        # Normalize storage settings to handle both variable naming conventions
        # Handle bucket name
        if not self.USER_IMAGES_BUCKET and self.S3_BUCKET_NAME:
            object.__setattr__(self, "USER_IMAGES_BUCKET", self.S3_BUCKET_NAME)

        # Handle region
        if not self.AWS_REGION or self.AWS_REGION == "auto":
            if self.AWS_DEFAULT_REGION:
                object.__setattr__(self, "AWS_REGION", self.AWS_DEFAULT_REGION)
            else:
                object.__setattr__(self, "AWS_REGION", "auto")

        # Handle endpoint URL
        if not self.S3_ENDPOINT_URL and self.AWS_ENDPOINT_URL:
            object.__setattr__(self, "S3_ENDPOINT_URL", self.AWS_ENDPOINT_URL)

        return self

    # CORS settings
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

    @property
    def allowed_origins_list(self) -> list[str]:
        """Get ALLOWED_ORIGINS as a list."""
        origins = []
        if self.ALLOWED_ORIGINS:
            origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

        # Allow null origin for Chrome extensions (service workers send null origin)
        # Also allow chrome-extension:// origins for extension popups/content scripts
        origins.append("null")

        return origins

    # Runtime environment settings
    PORT: int = 8000
    APP_ENVIRONMENT: str = "development"  # Set to "production" on App Runner via Terraform
    RUN_STARTUP_TASKS: bool = Field(
        default=True,
        description="Run lifespan startup work (car generation seed, orphan job sweep). Lambda sets this false.",
    )

    # DynamoDB settings
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
        return self.DYNAMODB_TABLE_PREFIX or f"carmodpicker-{self.APP_ENVIRONMENT.lower()}"

    # Security settings
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return not self.DEBUG and self.APP_ENVIRONMENT.lower() != "development"

    @property
    def secure_cookies(self) -> bool:
        """Determine if cookies should use secure flag (HTTPS only)."""
        return self.is_production

    # Email settings
    EMAIL_ENABLED: bool = Field(
        default=False,
        description=(
            "Enable email sending via SES. Set to true in production. " "When false, email calls are silently skipped."
        ),
    )
    EMAIL_FROM: str = Field(default="")

    # Sentry settings (Phase 2 / OBS-01)
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

    # Rate limiting settings
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000

    # Sophisticated rate limiting settings
    RATE_LIMIT_GET_REQUESTS_PER_MINUTE: int = 200
    RATE_LIMIT_GET_REQUESTS_PER_HOUR: int = 20000
    RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE: int = 10
    RATE_LIMIT_AUTH_REQUESTS_PER_HOUR: int = 100
    RATE_LIMIT_ADMIN_REQUESTS_PER_MINUTE: int = 30
    RATE_LIMIT_ADMIN_REQUESTS_PER_HOUR: int = 300

    # Layer 2: the shared, DynamoDB backed limiter. Layer 1 is the in-memory limiter
    # above, which stays because it is free and absorbs a burst inside one execution
    # environment before any network call happens. Layer 2 is what makes a limit hold
    # across execution environments and, after the split, across the nine functions.
    #
    # The table name is not configurable. It is `<prefix>-rate-limits` by the platform
    # standard, resolved from DYNAMODB_TABLE_PREFIX like every other table, and
    # RATE_LIMITS_TABLE below exists only so the deployed function can be pointed at a
    # differently named table without a code change. Leaving it empty is the normal case.
    ENABLE_SHARED_RATE_LIMITING: bool = True
    RATE_LIMITS_TABLE: str = ""

    # S3 storage settings. On App Runner, these are set via Terraform env vars; credentials
    # come from the App Runner instance IAM role (AWS_ACCESS_KEY_ID/SECRET left empty).
    # Accepts alternative variable names for local dev flexibility.
    USER_IMAGES_BUCKET: str = Field(
        default="",
        description="S3 bucket name for user image uploads. Also accepts S3_BUCKET_NAME.",
    )
    # Chrome extension POST /crawled-pages/scrape: max UTF-8 byte length of the `html` field (reject with 413).
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
    # Image upload settings
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
        """Get allowed image extensions as a list."""
        if not self.ALLOWED_IMAGE_EXTENSIONS:
            return []
        return [ext.strip().lower() for ext in self.ALLOWED_IMAGE_EXTENSIONS.split(",") if ext.strip()]

    @property
    def max_image_size_bytes(self) -> int:
        """Get maximum image size in bytes."""
        return self.MAX_IMAGE_SIZE_MB * 1024 * 1024

    APP_SECRETS_ARN: str = Field(
        default="",
        description=(
            "ARN of the one JSON secret holding SECRET_FIELDS. Empty = secrets come "
            "from the environment only and no Secrets Manager call is ever made."
        ),
    )

    # --- Lazily resolved secrets -------------------------------------------------
    #
    # Each SECRET_FIELDS name is stored in a `<NAME>_SETTING` field populated from
    # the environment (via the field alias) and read back through a property that
    # falls back to Secrets Manager only when the environment left it empty. The
    # fetch is cached in app.core.secrets for the life of the execution
    # environment, so the first read of the first secret pays the call and nothing
    # after it does.

    def _resolve_secret(self, name: str) -> str:
        # The live environment is consulted first, not just the value captured
        # when this Settings was built. `settings` is a module level singleton
        # constructed at import, so reading os.environ here preserves the old
        # behaviour of picking up a value exported after that point, which the
        # test suite and the crawler entrypoints both rely on.
        from_env = os.environ.get(name, "") or getattr(self, f"{name}_SETTING", "")
        if from_env:
            return from_env
        arn = os.environ.get("APP_SECRETS_ARN", "") or self.APP_SECRETS_ARN
        if not arn:
            return ""
        return fetch_app_secrets(arn).get(name, "")

    @property
    def SECRET_KEY(self) -> str:
        return self._resolve_secret("SECRET_KEY")

    @property
    def SENTRY_DSN(self) -> str:
        return self._resolve_secret("SENTRY_DSN")

    def require_secrets(self, *names: str) -> None:
        """Raise unless every named secret resolves to a non-empty value.

        Call this at the point of use, not at import. It replaces the import
        time validator that used to warn about an empty SECRET_KEY: a function
        that signs tokens fails loudly at startup, and one that does not, such
        as an entirely read only domain, never asks and never needs the grant.
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
    """
    Get cached settings.
    For tests, this can be overridden before the first call.
    """
    return Settings()


# No secret is read here. Importing this module makes no network call and needs
# no AWS credentials, which is what lets every per domain entrypoint be imported
# by tooling and by the route contract test.
settings = get_settings()
