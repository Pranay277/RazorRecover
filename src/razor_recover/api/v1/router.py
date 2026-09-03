"""V1 API router – collects all v1 endpoint routers."""

from fastapi import APIRouter

from src.razor_recover.api.v1.endpoints.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
