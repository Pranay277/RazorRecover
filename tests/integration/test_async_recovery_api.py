"""Integration tests for the async recovery endpoints.

The task queue is faked - no Redis or Celery broker is required. Also confirms
the existing synchronous endpoint remains functional (no workflow regression).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from razor_recover.api import dependencies
from razor_recover.core.database import Base
from razor_recover.main import create_app
from razor_recover.tasks.schemas import TaskStatusResponse
from razor_recover.workflow.schemas import EvaluateResponse


class FakeQueue:
    """In-memory queue adapter that never touches a broker."""

    def __init__(self):
        self.enqueued: list[int] = []
        self.statuses: dict[str, TaskStatusResponse] = {}

    def enqueue(self, transaction_id: int) -> str:
        self.enqueued.append(transaction_id)
        return f"task-{transaction_id}"

    def get_task_status(self, task_id: str) -> TaskStatusResponse:
        return self.statuses.get(
            task_id, TaskStatusResponse(task_id=task_id, status="PENDING")
        )


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = session_factory()

    queue = FakeQueue()
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[dependencies.db_session] = override_db
    app.dependency_overrides[dependencies.get_recovery_task_queue] = lambda: queue

    with TestClient(app) as test_app:
        test_app._queue = queue  # type: ignore[attr-defined]
        yield test_app

    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_async_endpoint_returns_queued(client):
    resp = client.post("/api/v1/recovery/evaluate/async", json={"transaction_id": 3879})
    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"] == "task-3879"
    assert body["status"] == "queued"
    assert body["transaction_id"] == 3879
    assert client._queue.enqueued == [3879]  # type: ignore[attr-defined]


def test_async_endpoint_does_not_execute_workflow_synchronously(client):
    ran: list[int] = []

    class NoopOrchestrator:
        def evaluate(self, session, transaction_id: int):
            ran.append(transaction_id)
            raise AssertionError("async endpoint must not run the workflow inline")

    client.app.dependency_overrides[  # type: ignore[attr-defined]
        dependencies.get_recovery_orchestrator
    ] = lambda: NoopOrchestrator()

    resp = client.post("/api/v1/recovery/evaluate/async", json={"transaction_id": 7})
    assert resp.status_code == 202
    assert ran == []


def test_async_endpoint_rejects_invalid_transaction_id(client):
    resp = client.post("/api/v1/recovery/evaluate/async", json={"transaction_id": 0})
    assert resp.status_code == 422


def test_task_status_pending(client):
    client._queue.statuses["abc"] = TaskStatusResponse(task_id="abc", status="PENDING")  # type: ignore[attr-defined]
    resp = client.get("/api/v1/recovery/tasks/abc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == "abc"
    assert body["status"] == "PENDING"
    assert body["result"] is None
    assert body["error"] is None


def test_task_status_success(client):
    result = {"transaction_id": 12, "policy_decision": "ALLOW", "audit_id": 5}
    client._queue.statuses["ok"] = TaskStatusResponse(  # type: ignore[attr-defined]
        task_id="ok", status="SUCCESS", transaction_id=12, result=result
    )
    resp = client.get("/api/v1/recovery/tasks/ok")
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["transaction_id"] == 12
    assert body["result"] == result
    assert body["error"] is None


def test_task_status_failure_is_safe(client):
    client._queue.statuses["bad"] = TaskStatusResponse(  # type: ignore[attr-defined]
        task_id="bad", status="FAILURE", error="Recovery evaluation failed."
    )
    resp = client.get("/api/v1/recovery/tasks/bad")
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"] == "Recovery evaluation failed."
    assert "Traceback" not in body["error"]
    assert body["result"] is None


def test_task_status_polling_never_enqueues_another_task(client):
    client._queue.statuses["abc"] = TaskStatusResponse(task_id="abc", status="STARTED")  # type: ignore[attr-defined]
    client.get("/api/v1/recovery/tasks/abc")
    client.get("/api/v1/recovery/tasks/abc")
    assert client._queue.enqueued == []  # type: ignore[attr-defined]


def test_sync_endpoint_remains_functional(client):
    class StubOrchestrator:
        def evaluate(self, session, transaction_id: int) -> EvaluateResponse:
            return EvaluateResponse(
                transaction_id=transaction_id,
                policy_decision="ALLOW",
                execution_status="recovered",
                recovery_status="recovered",
                audit_id=1,
            )

    client.app.dependency_overrides[  # type: ignore[attr-defined]
        dependencies.get_recovery_orchestrator
    ] = lambda: StubOrchestrator()

    resp = client.post("/api/v1/recovery/evaluate", json={"transaction_id": 9})
    assert resp.status_code == 200
    body = resp.json()
    assert body["transaction_id"] == 9
    assert body["policy_decision"] == "ALLOW"
    assert body["execution_status"] == "recovered"