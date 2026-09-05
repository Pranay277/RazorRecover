"""Recovery evaluation endpoint (public HTTP entry point for the workflow).

This endpoint is intentionally thin - it only parses input, delegates to the
orchestration service, and maps workflow errors to HTTP status codes. No
business logic lives here.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from razor_recover.api.dependencies import db_session, get_recovery_orchestrator
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
