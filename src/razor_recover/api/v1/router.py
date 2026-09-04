"""V1 API router – collects all v1 endpoint routers."""

from fastapi import APIRouter

from src.razor_recover.api.v1.endpoints.health import router as health_router
from src.razor_recover.api.v1.endpoints.recovery import router as recovery_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(recovery_router, tags=["recovery"])
