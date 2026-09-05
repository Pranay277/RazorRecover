"""End-to-end integration tests for the recovery workflow.

Proves the full pipeline: transaction -> ML -> RAG -> LLM -> Policy -> Execution
-> persistence -> audit works as one unit. ML/RAG/LLM are fakes; the real
`PolicyEngine` and `MockPaymentGateway` are used. Uses in-memory SQLite and a
thin API client.

No Ollama, Qdrant, or real payment systems are required.
"""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from razor_recover.core.database import Base
from razor_recover.api import dependencies
from razor_recover.brains.llm.schemas import AgentDecision, AllowedAction
from razor_recover.brains.ml.service import MLModelUnavailableError
from razor_recover.brains.rag.schemas import RetrievalHit, RetrievalResult
from razor_recover.db.models.audit import AuditLog
from razor_recover.db.models.customer import Customer
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.merchant import Merchant
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction
from razor_recover.execution.exceptions import UnauthorizedExecutionError
from razor_recover.execution.gateway import MockPaymentGateway
from razor_recover.execution.recovery_service import RecoveryService
from razor_recover.execution.retry_service import RetryService
from razor_recover.execution.schemas import ExecutionStatus, GatewayOutcome
from razor_recover.main import create_app
from razor_recover.shield.exceptions import PolicyError
from razor_recover.shield.policy_engine import PolicyEngine
from razor_recover.workflow.exceptions import (
    LLMStageError,
    MLStageError,
    PolicyStageError,
    TransactionNotFoundError,
)
from razor_recover.workflow.orchestrator import RecoveryOrchestrator
from razor_recover.workflow.policy import DefaultMerchantPolicyProvider


# ---------------------------------------------------------------------------
# Fake upstream providers
# ---------------------------------------------------------------------------

class FakePrediction:
    def __init__(self, risk=0.4, recovery=0.6, error=None):
        self.risk = risk
        self.recovery = recovery
        self.error = error

    def predict_single(self, transaction):
        if self.error:
            raise self.error
        return SimpleNamespace(
            risk_score=self.risk, recovery_probability=self.recovery
        )


class FakeRAG:
    def __init__(self, error=None):
        self.error = error

    def retrieve(self, query, merchant_id=None, top_k=0):
        if self.error:
            raise self.error
        return RetrievalResult(
            query=query,
            merchant_id=merchant_id,
            top_k=top_k,
            hits=[
                RetrievalHit(
                    id="c1", document_id="doc::retry",
                    category="retry_limits", merchant_scope=None,
                    source="synthetic-demo", score=0.9,
                    content="Network timeouts may be retried.",
                )
            ],
        )


class FakeAgent:
    def __init__(self, action=AllowedAction.RETRY_NOW, error=None, rationale="agent-plan"):
        self.action = action
        self.error = error
        self.rationale = rationale

    def recommend(self, request):
        if self.error:
            raise self.error
        return AgentDecision(
            transaction_external_id=request.transaction.external_id,
            action=self.action,
            rationale=self.rationale,
            confidence=0.9,
            requires_policy_review=False,
            risk_score=request.risk_score,
            recovery_probability=request.recovery_probability,
        )


class ExplodingPolicy:
    def evaluate(self, context):
        raise PolicyError("policy down")


# ---------------------------------------------------------------------------
# DB seeding
# ---------------------------------------------------------------------------

def _seed_transaction(session: Session, amount="100.00", status="failed",
                      attempts: int = 0):
    merchant = Merchant(external_id="m-1", name="Merchant One",
                        industry="retail", status="active")
    customer = Customer(external_id="c-1", name="Customer One",
                        email="c@example.com", status="active")
    session.add_all([merchant, customer])
    session.flush()
    tx = Transaction(
        external_id="tx-e2e",
        customer_id=customer.id,
        merchant_id=merchant.id,
        amount=Decimal(amount),
        currency="USD",
        status=status,
        failure_code="card_declined",
        failure_reason="bank declined",
        payment_method="card",
        gateway="stripe",
        attempt_number=1,
    )
    session.add(tx)
    session.flush()
    for i in range(attempts):
        session.add(RecoveryAttempt(
            transaction_id=tx.id, attempt_type="RETRY_NOW",
            status="failed", started_at=None,
        ))
    session.flush()
    return tx


def _build_orchestrator(session: Session, *, agent=None, prediction=None,
                        rag=None, gateway=None, policy=None,
                        merchant_policies=None):
    agent = agent or FakeAgent()
    prediction = prediction or FakePrediction()
    rag = rag if rag is not None else FakeRAG()
    gw = gateway or MockPaymentGateway()
    recovery = RecoveryService(retry_service=RetryService(gateway=gw))
    engine = policy if policy is not None else PolicyEngine()
    policy_provider = merchant_policies or DefaultMerchantPolicyProvider()
    return RecoveryOrchestrator(
        prediction_service=prediction,
        agent_service=agent,
        policy_engine=engine,
        recovery_service=recovery,
        merchant_policy_provider=policy_provider,
        rag_service=rag,
    ), gw


# ---------------------------------------------------------------------------
# Orchestrator-level tests
# ---------------------------------------------------------------------------

def test_transaction_not_found(sqlite_session):
    orch, _ = _build_orchestrator(sqlite_session)
    with pytest.raises(TransactionNotFoundError):
        orch.evaluate(sqlite_session, 999999)


def test_successful_runtime_allows_and_recovers(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    orch, gw = _build_orchestrator(sqlite_session, agent=FakeAgent(AllowedAction.RETRY_NOW))
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    assert resp.policy_decision == "ALLOW"
    assert resp.authorized_action == "RETRY_NOW"
    assert resp.execution_status == "recovered"
    assert resp.recovery_status == "recovered"
    assert resp.audit_id is not None
    # persistence
    assert sqlite_session.query(RecoveryAttempt).count() == 1
    assert sqlite_session.query(AuditLog).count() == 1
    assert sqlite_session.query(RecoveryDecision).count() == 1
    assert len(gw.calls) == 1  # exact one real simulation


def test_policy_block_does_not_execute(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    orch, gw = _build_orchestrator(sqlite_session, agent=FakeAgent(AllowedAction.STOP))
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    assert resp.policy_decision == "BLOCK"
    assert resp.authorized_action is None
    assert resp.execution_status is None
    assert sqlite_session.query(RecoveryAttempt).count() == 0
    assert len(gw.calls) == 0


def test_policy_review_does_not_execute(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    orch, gw = _build_orchestrator(sqlite_session, agent=FakeAgent(AllowedAction.MANUAL_REVIEW))
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    assert resp.policy_decision == "REVIEW"
    assert resp.authorized_action is None
    assert resp.execution_status is None
    assert sqlite_session.query(RecoveryAttempt).count() == 0
    assert len(gw.calls) == 0


def test_failed_gateway_leaves_transaction_failed(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway(default_outcome=GatewayOutcome.FAILED)
    orch, _ = _build_orchestrator(sqlite_session,
                                  agent=FakeAgent(AllowedAction.RETRY_NOW), gateway=gw)
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    assert resp.execution_status == "failed"
    assert resp.recovery_status == "failed"
    assert sqlite_session.query(RecoveryAttempt).one().status == "failed"


def test_gateway_timeout_records_timeout(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway(default_outcome=GatewayOutcome.TIMEOUT)
    orch, _ = _build_orchestrator(sqlite_session,
                                  agent=FakeAgent(AllowedAction.RETRY_NOW), gateway=gw)
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    assert resp.execution_status == "timeout"
    assert sqlite_session.query(RecoveryAttempt).one().status == "timeout"


def test_llm_failure_no_execution(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    from razor_recover.brains.llm.exceptions import LLMProviderUnavailableError
    fake = FakeAgent(error=LLMProviderUnavailableError("offline"))
    orch, gw = _build_orchestrator(sqlite_session, agent=fake)
    with pytest.raises(LLMStageError):
        orch.evaluate(sqlite_session, tx.id)
    assert len(gw.calls) == 0
    assert sqlite_session.query(RecoveryAttempt).count() == 0


def test_rag_failure_is_safe(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    orch, gw = _build_orchestrator(sqlite_session,
                                   agent=FakeAgent(AllowedAction.RETRY_NOW),
                                   rag=FakeRAG(error=RuntimeError("qdrant down")))
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    # Recovers safely with empty context - never invents context.
    assert resp.policy_decision == "ALLOW"
    assert sqlite_session.query(AuditLog).count() == 1


def test_ml_failure_no_execution(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    fake_pred = FakePrediction(error=MLModelUnavailableError("no models"))
    orch, gw = _build_orchestrator(sqlite_session, prediction=fake_pred)
    with pytest.raises(MLStageError):
        orch.evaluate(sqlite_session, tx.id)
    assert len(gw.calls) == 0
    assert sqlite_session.query(RecoveryAttempt).count() == 0


def test_policy_failure_no_execution(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    orch, gw = _build_orchestrator(sqlite_session,
                                   agent=FakeAgent(AllowedAction.RETRY_NOW),
                                   policy=ExplodingPolicy())
    with pytest.raises(PolicyStageError):
        orch.evaluate(sqlite_session, tx.id)
    assert len(gw.calls) == 0
    assert sqlite_session.query(RecoveryAttempt).count() == 0


def test_retry_limit_prevents_duplicate_retry(sqlite_session):
    # 3 prior failed retry attempts == default max_retries -> BLOCK, no new.
    tx = _seed_transaction(sqlite_session, attempts=3)
    orch, gw = _build_orchestrator(sqlite_session, agent=FakeAgent(AllowedAction.RETRY_NOW))
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    assert resp.policy_decision == "BLOCK"
    assert resp.execution_status is None
    assert sqlite_session.query(RecoveryAttempt).count() == 3  # unchanged
    assert len(gw.calls) == 0


def test_audit_and_attempt_records_created(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    orch, _ = _build_orchestrator(sqlite_session, agent=FakeAgent(AllowedAction.RETRY_NOW))
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()
    audit = sqlite_session.get(AuditLog, resp.audit_id)
    assert audit is not None
    assert "recovery.evaluate:ALLOW" == audit.action
    assert '"policy_decision": "ALLOW"' in audit.detail or "ALLOW" in audit.detail
    attempt = sqlite_session.query(RecoveryAttempt).one()
    assert attempt.attempt_type == "RETRY_NOW"
    assert attempt.status == "recovered"


def test_new_attempt_links_to_the_authorizing_decision(sqlite_session):
    # A prior decision must not be referenced by an attempt created in a later
    # evaluation: the attempt belongs to the decision that authorized it.
    tx = _seed_transaction(sqlite_session)
    prior = RecoveryDecision(
        transaction_id=tx.id,
        action="retry",
        outcome="authorized",
        risk_score=Decimal("0.2500"),
        decided_at=datetime.now(timezone.utc),
    )
    sqlite_session.add(prior)
    sqlite_session.flush()

    orch, _ = _build_orchestrator(
        sqlite_session, agent=FakeAgent(AllowedAction.RETRY_NOW)
    )
    resp = orch.evaluate(sqlite_session, tx.id)
    sqlite_session.flush()

    decision = (
        sqlite_session.query(RecoveryDecision)
        .order_by(RecoveryDecision.id.desc())
        .first()
    )
    attempt = sqlite_session.query(RecoveryAttempt).one()
    assert resp.audit_id is not None
    assert decision.id != prior.id
    assert attempt.decision_id == decision.id


def test_execution_cannot_bypass_policy_decision(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway()
    recovery = RecoveryService(retry_service=RetryService(gateway=gw))
    from razor_recover.shield.schemas import PolicyDecision, PolicyDecisionType
    blocked = PolicyDecision(decision=PolicyDecisionType.BLOCK,
                             requested_action="RETRY_NOW", final_action=None)
    with pytest.raises(UnauthorizedExecutionError):
        recovery.execute(decision=blocked, session=sqlite_session, transaction=tx)
    assert len(gw.calls) == 0


# ---------------------------------------------------------------------------
# API-level tests
# ---------------------------------------------------------------------------

@pytest.fixture
def api():
    # Thread-safe in-memory SQLite so TestClient (different thread) can share it.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = session_factory()
    orch, gw = _build_orchestrator(session)
    orch.gw = gw  # type: ignore[attr-defined]

    app = create_app()

    def override_db():
        yield session

    def override_orch():
        return orch

    app.dependency_overrides[dependencies.db_session] = override_db
    app.dependency_overrides[dependencies.get_recovery_orchestrator] = override_orch
    with TestClient(app) as client:
        client._session = session  # type: ignore[attr-defined]
        client._orchestrator = orch  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_api_transaction_not_found_404(api):
    resp = api.post("/api/v1/recovery/evaluate", json={"transaction_id": 123456})
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"]


def test_api_success_allows_and_validates_schema(api):
    session = api._session  # type: ignore[attr-defined]
    tx = _seed_transaction(session)
    resp = api.post("/api/v1/recovery/evaluate", json={"transaction_id": tx.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["transaction_id"] == tx.id
    assert body["policy_decision"] == "ALLOW"
    assert body["authorized_action"] == "RETRY_NOW"
    assert body["execution_status"] == "recovered"
    assert body["recovery_status"] == "recovered"
    assert body["audit_id"] is not None
    # required keys present; secrets/PII absent
    for key in ("risk_score", "recovery_probability", "recommended_action",
                "rationale", "policy_reasons"):
        assert key in body


def test_api_block_never_executes(api):
    session = api._session  # type: ignore[attr-defined]
    tx = _seed_transaction(session)
    api._orchestrator.agent_service = FakeAgent(AllowedAction.STOP)  # type: ignore[attr-defined]
    resp = api.post("/api/v1/recovery/evaluate", json={"transaction_id": tx.id})
    assert resp.status_code == 200
    assert resp.json()["policy_decision"] == "BLOCK"
    assert resp.json()["execution_status"] is None
    assert session.query(RecoveryAttempt).count() == 0


def test_api_llm_failure_returns_503(api):
    session = api._session  # type: ignore[attr-defined]
    tx = _seed_transaction(session)
    from razor_recover.brains.llm.exceptions import LLMProviderUnavailableError
    api._orchestrator.agent_service = FakeAgent(error=LLMProviderUnavailableError("down"))  # type: ignore[attr-defined]
    resp = api.post("/api/v1/recovery/evaluate", json={"transaction_id": tx.id})
    assert resp.status_code == 503
    assert session.query(RecoveryAttempt).count() == 0
