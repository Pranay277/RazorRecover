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
    database_url: str = (
        "postgresql+psycopg://razor:razor_dev_password@localhost:5433/razorrecover"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # RAG / knowledge base
    qdrant_collection: str = "razorrecover_knowledge"
    rag_default_top_k: int = 5

    # Embedding provider: "hash" (deterministic, local - default for demo/tests)
    # or "ollama" (remote HTTP provider selected by rag_embedding_model).
    rag_embedding_provider: str = "hash"
    rag_embedding_model: str = "nomic-embed-text"
    rag_embedding_dim: int = 256

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""
    return Settings()