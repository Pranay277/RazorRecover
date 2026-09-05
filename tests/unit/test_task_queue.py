"""Tests for the task queue adapter (status mapping + safe error surfacing).

Uses a fake Celery app/result so no broker is required.
"""

from razor_recover.tasks.queue import RecoveryTaskQueue
from razor_recover.tasks.recovery_task import RecoveryTaskError
from razor_recover.tasks.schemas import TaskStatusResponse


class FakeResult:
    def __init__(self, state, result=None):
        self.state = state
        self.result = result


class FakeApp:
    def __init__(self, result):
        self._result = result

    def AsyncResult(self, task_id):  # noqa: N802 - mirrors Celery API
        return self._result


def _queue_for(result: FakeResult) -> RecoveryTaskQueue:
    return RecoveryTaskQueue(app=FakeApp(result), task=None)


def test_status_maps_success_with_result_and_transaction_id():
    result = {
        "transaction_id": 7,
        "policy_decision": "ALLOW",
        "audit_id": 42,
    }
    status = _queue_for(FakeResult("SUCCESS", result)).get_task_status("task-1")
    assert status == TaskStatusResponse(task_id="task-1", transaction_id=7,
                                        status="SUCCESS", result=result, error=None)


def test_status_maps_pending():
    status = _queue_for(FakeResult("PENDING")).get_task_status("task-1")
    assert status.status == "PENDING"
    assert status.result is None
    assert status.error is None


def test_status_maps_started():
    status = _queue_for(FakeResult("STARTED")).get_task_status("task-1")
    assert status.status == "STARTED"
    assert status.result is None


def test_status_maps_known_task_error_to_safe_message():
    error = RecoveryTaskError("Transaction 404 does not exist.")
    status = _queue_for(FakeResult("FAILURE", error)).get_task_status("task-1")
    assert status.status == "FAILURE"
    assert status.error == "Transaction 404 does not exist."
    assert status.result is None
    assert "Traceback" not in status.error


def test_status_maps_unknown_failure_to_generic_safe_message():
    status = _queue_for(FakeResult("FAILURE", RuntimeError("secret internal details"))).get_task_status("task-1")
    assert status.status == "FAILURE"
    assert status.error == "Asynchronous recovery evaluation failed."
    assert "secret internal details" not in status.error


def test_status_maps_revoked_to_failure():
    status = _queue_for(FakeResult("REVOKED")).get_task_status("task-1")
    assert status.status == "FAILURE"