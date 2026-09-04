"""Read-only summary endpoint for the merchant dashboard."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.razor_recover.api.dependencies import db_session, get_dashboard_read_service
from src.razor_recover.schemas.dashboard import SummaryResponse
from src.razor_recover.services.read.dashboard import DashboardReadService

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=SummaryResponse)
def get_summary(
    db: Session = Depends(db_session),
    service: DashboardReadService = Depends(get_dashboard_read_service),
) -> SummaryResponse:
    """Return dashboard summary metrics computed only from persisted data."""
    return service.get_summary(db)
