from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openrouter_api_key: str = ""

    cheap_model: str = "openrouter/free"
    strong_model: str = "openai/gpt-4o"

    # Pre-router threshold: obvious hard tasks go directly to the strong tier.
    routing_threshold: int = 5

    # Cheap-result quality threshold: below this, auto mode escalates.
    quality_threshold: float = 0.78

    max_files: int = 80
    max_file_chars: int = 12_000
    max_repo_chars: int = 180_000
    max_output_tokens: int = 3000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
