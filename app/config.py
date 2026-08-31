from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    max_files: int = 80
    max_file_chars: int = 12_000
    max_repo_chars: int = 180_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
