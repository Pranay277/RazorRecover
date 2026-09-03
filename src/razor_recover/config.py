"""Application configuration loaded from environment variables and .env files."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    Values are read from environment variables, falling back to a local
    .env file. All secrets must be provided via the environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "RazorRecover"
    app_env: str = "development"
    debug: bool = False

    # PostgreSQL
    database_url: str = "postgresql://user:password@localhost:5432/razor_recover"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""
    return Settings()