"""Recovery evaluation endpoints (public HTTP entry points for the workflow).

This router stays intentionally thin - it parses input, delegates to the
orchestration service (sync) or the task queue adapter (async), and maps
workflow errors to HTTP status codes. No business logic lives here.

Sync flow:   POST  /recovery/evaluate         -> orchestrator (unchanged)
Async flow:  POST  /recovery/evaluate/async   -> enqueue Celery task
             GET   /recovery/tasks/{task_id}  -> task status (poll)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from razor_recover.api.dependencies import (
    db_session,
    get_recovery_orchestrator,
    get_recovery_task_queue,
)
from razor_recover.tasks.queue import RecoveryTaskQueue
from razor_recover.tasks.schemas import TaskAccepted, TaskStatusResponse
from razor_recover.workflow.exceptions import (
    TransactionNotFoundError,
    WorkflowError,
    WorkflowStageError,
)
from razor_recover.workflow.orchestrator import RecoveryOrchestrator
from razor_recover.workflow.schemas import EvaluateRequest, EvaluateResponse

router = APIRouter()


@router.post(
    "/recovery/evaluate",
    response_model=EvaluateResponse,
    status_code=status.HTTP_200_OK,
)
def evaluate_recovery(
    payload: EvaluateRequest,
    db: Session = Depends(db_session),
    orchestrator: RecoveryOrchestrator = Depends(get_recovery_orchestrator),
) -> EvaluateResponse:
    """Run the full recovery workflow for one transaction."""
    try:
        return orchestrator.evaluate(db, payload.transaction_id)
    except TransactionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except WorkflowStageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except WorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router.post(
    "/recovery/evaluate/async",
    response_model=TaskAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def evaluate_recovery_async(
    payload: EvaluateRequest,
    queue: RecoveryTaskQueue = Depends(get_recovery_task_queue),
) -> TaskAccepted:
    """Enqueue a recovery evaluation; the worker runs the existing workflow."""
    task_id = queue.enqueue(payload.transaction_id)
    return TaskAccepted(task_id=task_id, transaction_id=payload.transaction_id)


@router.get("/recovery/tasks/{task_id}", response_model=TaskStatusResponse)
def get_recovery_task_status(
    task_id: str,
    queue: RecoveryTaskQueue = Depends(get_recovery_task_queue),
) -> TaskStatusResponse:
    """Return a stable view of one asynchronous recovery task.

    Polling this endpoint never enqueues another task.
    """
    return queue.get_task_status(task_id)