"""Celery application for asynchronously executed recovery work.

Broker/backend URLs come from the application settings (``CELERY_BROKER_URL``
and ``CELERY_RESULT_BACKEND``) - never hardcoded in business logic. Constructing
the app is lazy: importing this module does not connect to Redis.
"""

from __future__ import annotations

from celery import Celery

from razor_recover.config import get_settings


def create_celery_app() -> Celery:
    """Build the Celery app from application settings."""
    settings = get_settings()
    app = Celery(
        "razorrecover",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["razor_recover.tasks.recovery_task"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_default_queue="recovery",
        result_expires=3600,
    )
    return app


celery_app = create_celery_app()

__all__ = ["celery_app", "create_celery_app"]