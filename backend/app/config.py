"""Environment-based configuration. All secrets come from the environment (or `.env` in development)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production", "test"] = "development"

    database_url: str = "postgresql+psycopg://baysahne:baysahne_dev_only@127.0.0.1:5433/baysahne"
    test_database_url: str = "postgresql+psycopg://baysahne:baysahne_dev_only@127.0.0.1:5433/baysahne_test"
    # Fail fast instead of hanging requests when the database is down or the pool is exhausted.
    db_connect_timeout_seconds: int = 5
    db_pool_timeout_seconds: int = 10

    # Required outside development. In development local media URLs always follow each request's host (see
    # storage.RequestOrigin), so leave it empty: a value here is only used outside requests (CLI, worker).
    public_api_base_url: str = ""
    admin_base_url: str = "http://localhost:3100"
    cors_allowed_origins: str = "http://localhost:3100"

    cookie_secure: bool = False
    session_ttl_hours: int = 12
    session_cookie_name: str = "bs_admin_session"
    invitation_ttl_hours: int = 72
    password_reset_ttl_minutes: int = 60
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    media_storage: Literal["local", "s3"] = "local"
    media_local_root: str = "./var/media"
    media_max_upload_mb: int = 15
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""

    email_backend: Literal["console", "file", "smtp"] = "console"
    email_from: str = "Bay Sahne <no-reply@example.invalid>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True

    push_provider: Literal["log", "expo", "fake"] = "log"
    expo_access_token: str = ""

    worker_interval_seconds: int = 30

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Accept plain postgres URLs from hosting providers and pin the psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        """Refuse to run production with development-grade settings instead of silently degrading."""
        if not self.public_api_base_url and not self.is_dev:
            # Host-derived media URLs are a development convenience; deployed APIs need a fixed public origin.
            raise ValueError("PUBLIC_API_BASE_URL must be set outside development")
        if self.app_env != "production":
            return self
        problems = []
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true")
        if self.email_backend != "smtp":
            problems.append("EMAIL_BACKEND must be smtp")
        if self.push_provider != "expo":
            problems.append("PUSH_PROVIDER must be expo")
        if "baysahne_dev_only" in self.database_url:
            problems.append("DATABASE_URL uses the development password")
        if not self.public_api_base_url.startswith("https://"):
            problems.append("PUBLIC_API_BASE_URL must be https")
        if not self.admin_base_url.startswith("https://"):
            problems.append("ADMIN_BASE_URL must be https")
        if any(o.strip().startswith("http://") for o in self.cors_allowed_origins.split(",") if o.strip()):
            problems.append("CORS_ALLOWED_ORIGINS must be https origins")
        if self.media_storage == "s3" and not (self.s3_bucket and self.s3_public_base_url):
            problems.append("S3_BUCKET and S3_PUBLIC_BASE_URL are required for s3 storage")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("development", "test")

    @property
    def media_root_path(self) -> Path:
        p = Path(self.media_local_root)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
