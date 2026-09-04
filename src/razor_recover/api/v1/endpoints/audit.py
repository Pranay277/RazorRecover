"""Read-only audit trail endpoint for the merchant dashboard."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.razor_recover.api.dependencies import db_session, get_dashboard_read_service
from src.razor_recover.schemas.dashboard import AuditListResponse
from src.razor_recover.services.read.dashboard import DashboardReadService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditListResponse)
def list_audit_logs(
    transaction_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(db_session),
    service: DashboardReadService = Depends(get_dashboard_read_service),
) -> AuditListResponse:
    """List audit events (paginated), optionally filtered by transaction."""
    return service.list_audit_logs(
        db, transaction_id=transaction_id, limit=limit, offset=offset
    )
