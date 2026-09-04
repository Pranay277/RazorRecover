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

    # LLM / decision-agent provider configuration
    # Provider is "ollama" today; architecture allows others later.
    llm_provider: str = "ollama"
    llm_timeout_seconds: float = 60.0
    llm_temperature: float = 0.2
    llm_num_predict: int = 800

    # Policy / Safety Engine - RazorRecover demo defaults (NOT real Razorpay
    # limits). Merchant-specific values can override these per transaction.
    policy_version: int = 1
    policy_default_max_retries: int = 3
    policy_default_max_risk_score: float = 0.70
    policy_default_min_recovery_probability: float = 0.30
    policy_default_high_value_threshold: float = 10_000.0


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""
    return Settings()