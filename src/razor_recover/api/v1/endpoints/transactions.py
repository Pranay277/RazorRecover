"""Read-only transaction endpoints for the merchant dashboard.

These endpoints never execute or mutate anything - they return persisted
transactions, their recovery attempts, decisions, and audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.razor_recover.api.dependencies import db_session, get_dashboard_read_service
from src.razor_recover.schemas.dashboard import (
    TransactionDetail,
    TransactionListResponse,
)
from src.razor_recover.services.read.dashboard import DashboardReadService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    status_filter: str | None = Query(default=None, alias="status"),
    merchant_id: int | None = Query(default=None, ge=1),
    customer_id: int | None = Query(default=None, ge=1),
    payment_method: str | None = None,
    gateway: str | None = None,
    failure_code: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(db_session),
    service: DashboardReadService = Depends(get_dashboard_read_service),
) -> TransactionListResponse:
    """List transactions (paginated, filterable) for the dashboard."""
    return service.list_transactions(
        db,
        status=status_filter,
        merchant_id=merchant_id,
        customer_id=customer_id,
        payment_method=payment_method,
        gateway=gateway,
        failure_code=failure_code,
        limit=limit,
        offset=offset,
    )


@router.get("/{transaction_id}", response_model=TransactionDetail)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(db_session),
    service: DashboardReadService = Depends(get_dashboard_read_service),
) -> TransactionDetail:
    """Return one transaction with all persisted related records."""
    detail = service.get_transaction_detail(db, transaction_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} does not exist.",
        )
    return detail
