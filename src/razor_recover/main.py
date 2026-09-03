"""RazorRecover – FastAPI application entry point."""

from fastapi import FastAPI

from src.razor_recover.api.v1.router import api_router
from src.razor_recover.config import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint – confirms the service is reachable."""
        return {"message": f"Welcome to {settings.app_name}"}

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
