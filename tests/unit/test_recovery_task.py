"""Tests for the async recovery task adapter.

The task must invoke the EXISTING orchestrator (never duplicate the workflow),
return JSON-serializable results, and let failures surface as Celery FAILURE.
"""

import json
from types import SimpleNamespace

import pytest

import razor_recover.tasks.recovery_task as recovery_task_module
from razor_recover.tasks.recovery_task import (
    RecoveryTaskError,
    evaluate_recovery_task,
    run_recovery_evaluation,
)
from razor_recover.workflow.exceptions import LLMStageError, TransactionNotFoundError


class FakeSession:
    """Stand-in for a SQLAlchemy session; only needs to exist."""


def _fake_db():
    yield FakeSession()


def _fake_orchestrator(response, error=None):
    class FakeOrchestrator:
        def __init__(self):
            self.evaluate_calls = []

        def evaluate(self, session, transaction_id):
            self.evaluate_calls.append((session, transaction_id))
            if error is not None:
                raise error
            return response

    orch = FakeOrchestrator()
    return orch, orch.evaluate_calls


def test_task_invokes_existing_orchestrator(monkeypatch):
    payload = SimpleNamespace(model_dump=lambda mode="json": {
        "transaction_id": 42, "policy_decision": "ALLOW", "policy_reasons": [],
    })
    orch, calls = _fake_orchestrator(payload)
    monkeypatch.setattr(recovery_task_module, "build_orchestrator", lambda: orch)
    monkeypatch.setattr(recovery_task_module, "get_db", lambda: _fake_db())

    result = run_recovery_evaluation(42)

    assert result == {"transaction_id": 42, "policy_decision": "ALLOW", "policy_reasons": []}
    assert len(calls) == 1
    session, tx_id = calls[0]
    assert tx_id == 42
    assert isinstance(session, FakeSession)


def test_task_does_not_duplicate_workflow_logic(monkeypatch):
    """The task body is only an adapter - no ML/RAG/LLM/Policy/Execution code."""
    source = __import__(
        "razor_recover.tasks.recovery_task", fromlist=["recovery_task"]
    )
    body = source.__dict__
    for name in ("PredictionService", "RAGService", "DecisionAgentService",
                 "PolicyEngine", "RecoveryService", "AuditLog", "RecoveryAttempt"):
        assert name not in body
    assert "run_recovery_evaluation" in body
    assert "build_orchestrator" in body  # delegates to the existing workflow


def test_task_result_is_json_serializable(monkeypatch):
    payload = SimpleNamespace(model_dump=lambda mode="json": {
        "transaction_id": 7,
        "risk_score": 0.12,
        "recovery_probability": 0.88,
        "recommended_action": "RETRY_NOW",
        "policy_decision": "ALLOW",
        "authorized_action": "RETRY_NOW",
        "execution_status": "recovered",
        "recovery_status": "recovered",
        "rationale": "safe to retry",
        "policy_reasons": ["risk low"],
        "audit_id": 99,
    })
    orch, _ = _fake_orchestrator(payload)
    monkeypatch.setattr(recovery_task_module, "build_orchestrator", lambda: orch)
    monkeypatch.setattr(recovery_task_module, "get_db", lambda: _fake_db())

    result = run_recovery_evaluation(7)
    json.dumps(result)  # must not raise for any payload field


def test_unknown_transaction_becomes_task_failure(monkeypatch):
    orch, _ = _fake_orchestrator(
        None, error=TransactionNotFoundError("Transaction 999 does not exist.")
    )
    monkeypatch.setattr(recovery_task_module, "build_orchestrator", lambda: orch)
    monkeypatch.setattr(recovery_task_module, "get_db", lambda: _fake_db())

    with pytest.raises(RecoveryTaskError) as excinfo:
        evaluate_recovery_task.run(999)
    assert excinfo.value.safe_message == "Transaction 999 does not exist."


def test_stage_failure_becomes_safe_task_failure(monkeypatch):
    orch, _ = _fake_orchestrator(None, error=LLMStageError("LLM unavailable"))
    monkeypatch.setattr(recovery_task_module, "build_orchestrator", lambda: orch)
    monkeypatch.setattr(recovery_task_module, "get_db", lambda: _fake_db())

    with pytest.raises(RecoveryTaskError) as excinfo:
        evaluate_recovery_task.run(1)
    assert "nothing was executed" in excinfo.value.safe_message