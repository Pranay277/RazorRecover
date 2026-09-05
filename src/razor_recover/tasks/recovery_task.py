"""Asynchronous adapter around the existing recovery workflow.

This is the only task in the async layer. It does NOT re-implement ML, RAG, LLM,
Shield, execution, or audit logic - it simply invokes the exact same
:class:`razor_recover.workflow.orchestrator.RecoveryOrchestrator` used by the
synchronous endpoint. Expected workflow failures are converted to a safe
:class:`RecoveryTaskError` and re-raised so Celery records ``FAILURE``.
"""

from __future__ import annotations

from razor_recover.core.database import get_db
from razor_recover.tasks.celery_app import celery_app
from razor_recover.workflow.deps import build_orchestrator
from razor_recover.workflow.exceptions import (
    TransactionNotFoundError,
    WorkflowError,
    WorkflowStageError,
)


class RecoveryTaskError(Exception):
    """Async task failure carrying a safe, user-visible message."""

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


def run_recovery_evaluation(transaction_id: int) -> dict:
    """Run the existing orchestrator for one transaction; return JSON-safe data."""
    orchestrator = build_orchestrator()
    for db in get_db():
        response = orchestrator.evaluate(db, transaction_id)
    return response.model_dump(mode="json")


@celery_app.task(name="recovery.evaluate_async", max_retries=0)
def evaluate_recovery_task(transaction_id: int) -> dict:
    """Celery task: execute the existing recovery workflow asynchronously."""
    try:
        return run_recovery_evaluation(transaction_id)
    except TransactionNotFoundError as exc:
        raise RecoveryTaskError(
            f"Transaction {transaction_id} does not exist."
        ) from exc
    except WorkflowStageError as exc:
        raise RecoveryTaskError(
            "A recovery pipeline stage failed; nothing was executed."
        ) from exc
    except WorkflowError as exc:
        raise RecoveryTaskError("Recovery evaluation failed.") from exc


__all__ = [
    "RecoveryTaskError",
    "evaluate_recovery_task",
    "run_recovery_evaluation",
]