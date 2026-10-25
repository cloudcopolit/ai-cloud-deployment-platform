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


settings = Settings()
