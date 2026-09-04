"""V1 API router – collects all v1 endpoint routers."""

from fastapi import APIRouter

from src.razor_recover.api.v1.endpoints.audit import router as audit_router
from src.razor_recover.api.v1.endpoints.health import router as health_router
from src.razor_recover.api.v1.endpoints.recovery import router as recovery_router
from src.razor_recover.api.v1.endpoints.summary import router as summary_router
from src.razor_recover.api.v1.endpoints.transactions import router as transactions_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(recovery_router, tags=["recovery"])
api_router.include_router(transactions_router, tags=["transactions"])
api_router.include_router(summary_router, tags=["summary"])
api_router.include_router(audit_router, tags=["audit"])
