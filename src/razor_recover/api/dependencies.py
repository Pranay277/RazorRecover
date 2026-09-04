"""Reusable FastAPI dependencies.

As a rule the API never instantiates DB engines, LLM providers, Qdrant clients,
ML models or gateways inline. Heavy/stateful services are built once behind a
composition root and injected as dependencies.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from src.razor_recover.core.database import get_db
from src.razor_recover.workflow.deps import build_orchestrator
from src.razor_recover.workflow.orchestrator import RecoveryOrchestrator


def db_session() -> Generator[Session, None, None]:
    """Dependency that provides a database session to request handlers."""
    yield from get_db()


@lru_cache
def _orchestrator() -> RecoveryOrchestrator:
    return build_orchestrator()


def get_recovery_orchestrator() -> RecoveryOrchestrator:
    """Provide the (cached) recovery workflow orchestrator."""
    return _orchestrator()


__all__ = ["db_session", "get_recovery_orchestrator"]
