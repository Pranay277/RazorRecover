"""Tests for the Celery application configuration and task registration.

No broker/Redis is required - constructing the app and registering tasks is
fully lazy.
"""

from razor_recover.config import Settings, get_settings
from razor_recover.tasks.celery_app import celery_app


def test_celery_app_uses_settings_for_broker_and_backend():
    settings = get_settings()
    assert celery_app.conf.broker_url == settings.celery_broker_url
    assert celery_app.conf.result_backend == settings.celery_result_backend


def test_celery_defaults_point_at_local_redis_db0_and_db1(monkeypatch):
    for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.celery_broker_url == "redis://localhost:6379/0"
    assert settings.celery_result_backend == "redis://localhost:6379/1"


def test_celery_uses_json_serialization():
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert "json" in celery_app.conf.accept_content


def test_celery_tracks_started_state():
    assert celery_app.conf.task_track_started is True


def test_recovery_task_registered_with_celery_app():
    task = celery_app.tasks.get("recovery.evaluate_async")
    assert task is not None
    assert task.name == "recovery.evaluate_async"