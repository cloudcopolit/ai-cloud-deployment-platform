from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str
    environment: Literal["development", "test", "staging", "production"] = "development"

    jwt_secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"
    github_client_id: str
    github_client_secret: str
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"

    # Repository access (ADR-021). All optional: without them only public repositories are
    # reachable, anonymously (60 requests/hour).
    github_token: str | None = None
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_app_private_key_path: str | None = None
    github_webhook_secret: str | None = None  # webhook endpoint answers 404 while unset
    github_api_url: str = "https://api.github.com"
    github_raw_url: str = "https://raw.githubusercontent.com"

    # Background jobs (ADR-008). Defaults follow 06 §3.5.
    job_timeout_s: int = Field(600, ge=10)
    worker_poll_interval_s: float = Field(1.0, gt=0)
    worker_heartbeat_interval_s: float = Field(5.0, gt=0)
    worker_stale_after_s: int = Field(60, ge=5)  # no heartbeat for this long = worker lost
    job_max_attempts: int = Field(2, ge=1)  # a lost job is re-queued until this many attempts
    max_active_jobs_per_team: int = Field(5, ge=1)


settings = Settings()
