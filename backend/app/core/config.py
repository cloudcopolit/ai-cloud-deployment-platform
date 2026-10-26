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
    # dev only: repositories of this owner come from a local mirror of examples/ (never in
    # production); used to analyze CloudPilot's own reference app without a public repo
    github_dev_mirror_url: str | None = None
    github_dev_mirror_owner: str = "cloudpilot-examples"

    # Background jobs (ADR-008). Defaults follow 06 §3.5.
    job_timeout_s: int = Field(600, ge=10)
    worker_poll_interval_s: float = Field(1.0, gt=0)
    worker_heartbeat_interval_s: float = Field(5.0, gt=0)
    worker_stale_after_s: int = Field(60, ge=5)  # no heartbeat for this long = worker lost
    job_max_attempts: int = Field(2, ge=1)  # a lost job is re-queued until this many attempts
    max_active_jobs_per_team: int = Field(5, ge=1)

    # Architecture (ADR-023): priced, deployable patterns; off = prototype template only.
    architect_automated_archetypes: bool = False

    # CloudPilot's own AWS identity (ADR-028). Never the ambient AWS_* (LocalStack) values.
    cloudpilot_aws_access_key_id: str | None = None
    cloudpilot_aws_secret_access_key: str | None = None
    cloudpilot_aws_region: str = "us-east-1"
    cloudpilot_aws_endpoint_url: str | None = None  # LocalStack in tests; empty = real AWS

    # Deployments (ADR-029/032/033)
    deploy_monthly_cost_cap_usd: float = Field(100.0, gt=0)
    deploy_approval_ttl_hours: int = Field(24, ge=1)
    deploy_runner_stale_after_s: int = Field(300, ge=60)
    deploy_job_timeout_s: int = Field(5400, ge=600)  # apply + RDS + health check

    # Rate limits (ADR-031)
    rate_limit_enabled: bool = True
    rate_limit_ip_per_minute: int = Field(120, ge=1)
    trusted_proxies: str = ""  # comma-separated peer IPs whose X-Forwarded-For is trusted

    # Language models (ADR-022). A provider without a key is never called (MOCKED-ONLY).
    llm_provider_priority: str = "anthropic,openai,gemini,xai"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    xai_api_key: str | None = None
    # Optional: pin a model per provider; honored only if the provider lists it.
    llm_model_anthropic: str | None = None
    llm_model_openai: str | None = None
    llm_model_gemini: str | None = None
    llm_model_xai: str | None = None
    # Optional "input,output" USD per 1M tokens; without it cost is reported as unknown.
    llm_price_anthropic: str | None = None
    llm_price_openai: str | None = None
    llm_price_gemini: str | None = None
    llm_price_xai: str | None = None
    llm_max_calls_per_job: int = Field(6, ge=0)
    llm_max_tokens_per_job: int = Field(60_000, ge=0)


settings = Settings()
