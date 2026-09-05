"""Service adapter between the HTTP layer and the Celery task queue.

The API endpoints never touch Celery objects directly - they talk to this
adapter, so the async transport stays swappable and the endpoints stay thin.
"""

from __future__ import annotations

from razor_recover.tasks.celery_app import celery_app
from razor_recover.tasks.recovery_task import RecoveryTaskError, evaluate_recovery_task
from razor_recover.tasks.schemas import TaskStatusResponse

_TRANSIENT_STATES = frozenset({"STARTED", "RETRY"})


class RecoveryTaskQueue:
    """Enqueue recovery evaluations and inspect their status."""

    def __init__(self, app=None, task=None) -> None:
        self._app = app or celery_app
        self._task = task or evaluate_recovery_task

    def enqueue(self, transaction_id: int) -> str:
        """Dispatch one evaluation to the worker; returns the task id."""
        result = self._task.apply_async(args=[transaction_id])
        return result.id

    def get_task_status(self, task_id: str) -> TaskStatusResponse:
        """Return a stable view of one task (never enqueues anything)."""
        result = self._app.AsyncResult(task_id)
        state = self._normalized_state(result.state)

        if state == "SUCCESS":
            payload = result.result if isinstance(result.result, dict) else None
            return TaskStatusResponse(
                task_id=task_id,
                transaction_id=(payload or {}).get("transaction_id"),
                status=state,
                result=payload,
            )
        if state == "FAILURE":
            return TaskStatusResponse(
                task_id=task_id,
                status=state,
                error=self._safe_failure_message(result),
            )
        return TaskStatusResponse(task_id=task_id, status=state)

    @staticmethod
    def _normalized_state(state: str) -> str:
        if state in {"FAILURE", "REVOKED"}:
            return "FAILURE"
        if state == "SUCCESS":
            return "SUCCESS"
        return "STARTED" if state in _TRANSIENT_STATES else "PENDING"

    @staticmethod
    def _safe_failure_message(result) -> str:
        try:
            error = result.result
        except Exception:  # noqa: BLE001 - never leak task internals
            error = None
        if (
            isinstance(error, RecoveryTaskError)
            and isinstance(error.safe_message, str)
            and error.safe_message
        ):
            return error.safe_message
        return "Asynchronous recovery evaluation failed."


__all__ = ["RecoveryTaskQueue"]