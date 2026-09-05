"""Reusable FastAPI dependencies.

As a rule the API never instantiates DB engines, LLM providers, Qdrant clients,
ML models or gateways inline. Heavy/stateful services are built once behind a
composition root and injected as dependencies.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from razor_recover.core.database import get_db
from razor_recover.services.read.dashboard import DashboardReadService
from razor_recover.tasks.queue import RecoveryTaskQueue
from razor_recover.workflow.deps import build_orchestrator
from razor_recover.workflow.orchestrator import RecoveryOrchestrator


def db_session() -> Generator[Session, None, None]:
    """Dependency that provides a database session to request handlers."""
    yield from get_db()


@lru_cache
def _orchestrator() -> RecoveryOrchestrator:
    return build_orchestrator()


def get_recovery_orchestrator() -> RecoveryOrchestrator:
    """Provide the (cached) recovery workflow orchestrator."""
    return _orchestrator()


def get_dashboard_read_service() -> DashboardReadService:
    """Provide a stateless dashboard read service."""
    return DashboardReadService()


@lru_cache
def _task_queue() -> RecoveryTaskQueue:
    return RecoveryTaskQueue()


def get_recovery_task_queue() -> RecoveryTaskQueue:
    """Provide the (cached) async recovery task queue adapter."""
    return _task_queue()


__all__ = [
    "db_session",
    "get_recovery_orchestrator",
    "get_dashboard_read_service",
    "get_recovery_task_queue",
]
