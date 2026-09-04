"""Integration tests for the read-only dashboard endpoints.

Confirms the four dashboard endpoints surface only persisted data, paginate and
filter correctly, return proper schemas, 404 on missing rows, handle empty
tables, and never mutate the database.

No auth, execution, or policy logic is involved here.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.razor_recover.api import dependencies
from src.razor_recover.core.database import Base
from src.razor_recover.db.models.audit import AuditLog
from src.razor_recover.db.models.customer import Customer
from src.razor_recover.db.models.decision import RecoveryDecision
from src.razor_recover.db.models.merchant import Merchant
from src.razor_recover.db.models.recovery import RecoveryAttempt
from src.razor_recover.db.models.transaction import Transaction
from src.razor_recover.main import create_app


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _seed(session: Session, *, audits: bool = True, attempts: bool = True,
          decisions: bool = True, recovered_tx: bool = True):
    merchant = Merchant(external_id="m-1", name="Acme Corp", industry="retail")
    customer = Customer(external_id="c-1", name="Jane Doe", email="jane@example.com")
    session.add_all([merchant, customer])
    session.flush()

    tx1 = Transaction(
        external_id="tx-1", customer_id=customer.id, merchant_id=merchant.id,
        amount=Decimal("100.00"), currency="USD", status="failed",
        failure_code="card_declined", failure_reason="bank declined",
        payment_method="card", gateway="stripe", attempt_number=2,
        attempted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    tx2 = Transaction(
        external_id="tx-2", customer_id=customer.id, merchant_id=merchant.id,
        amount=Decimal("50.00"), currency="USD", status="recovered",
        failure_code="network_error", failure_reason="timeout",
        payment_method="upi", gateway="razorpay", attempt_number=1,
        attempted_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    tx3 = Transaction(
        external_id="tx-3", customer_id=customer.id, merchant_id=merchant.id,
        amount=Decimal("200.00"), currency="INR", status="failed",
        failure_code="insufficient_funds", gateway="razorpay",
        attempted_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    session.add_all([tx1, tx2, tx3])
    session.flush()

    if decisions:
        session.add_all([
            RecoveryDecision(
                transaction_id=tx1.id, action="RETRY_NOW", outcome="authorized",
                risk_score=Decimal("0.4000"), rationale="high recovery prob",
                decided_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            RecoveryDecision(
                transaction_id=tx3.id, action="STOP", outcome="blocked",
                risk_score=Decimal("0.9000"), rationale="too risky",
                decided_at=datetime(2026, 3, 2, tzinfo=timezone.utc)),
        ])
        session.flush()
        decision_id = session.query(RecoveryDecision).filter_by(
            transaction_id=tx1.id).one().id
    else:
        decision_id = None

    if attempts:
        session.add(RecoveryAttempt(
            transaction_id=tx1.id, decision_id=decision_id,
            status="recovered", attempt_type="RETRY_NOW",
            started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 2, 0, 1, tzinfo=timezone.utc),
        ))
        session.flush()

    if audits:
        session.add_all([
            AuditLog(
                transaction_id=tx1.id, actor="recovery.workflow",
                action="recovery.evaluate:ALLOW",
                detail='{"policy_decision": "ALLOW", "execution_status": "recovered"}',
                occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            AuditLog(
                transaction_id=None, actor="system",
                action="system.startup",
                detail='{"booting": true}',
                occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ])
        session.flush()
    session.flush()
    return merchant, customer


# ---------------------------------------------------------------------------
# API fixture (thread-safe in-memory SQLite + TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = session_factory()

    app = create_app()

    def override_db():
        yield session

    def override_read_service():
        from src.razor_recover.services.read.dashboard import DashboardReadService
        return DashboardReadService()

    app.dependency_overrides[dependencies.db_session] = override_db
    app.dependency_overrides[
        dependencies.get_dashboard_read_service
    ] = override_read_service
    with TestClient(app) as client:
        client._session = session  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def _snapshot(session: Session) -> dict:
    return {
        "transactions": session.query(Transaction).count(),
        "decisions": session.query(RecoveryDecision).count(),
        "attempts": session.query(RecoveryAttempt).count(),
        "audits": session.query(AuditLog).count(),
    }


# ---------------------------------------------------------------------------
# Transactions list
# ---------------------------------------------------------------------------


def test_list_transactions_empty(api):
    resp = api.get("/api/v1/transactions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_transactions_returns_rows_and_schema(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    item = body["items"][0]
    for key in ("id", "external_id", "amount", "currency", "status",
                "failure_code", "failure_reason", "payment_method", "gateway",
                "attempt_number", "attempted_at", "merchant_external_id",
                "customer_external_id", "customer_id", "merchant_id",
                "created_at"):
        assert key in item
    # non-sensitive external ids present; names/emails absent from list
    assert item["merchant_external_id"] == "m-1"
    assert item["customer_external_id"] == "c-1"
    assert "email" not in item


def test_list_transactions_filters_by_status(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions", params={"status": "failed"})
    body = resp.json()
    assert body["total"] == 2
    assert all(t["status"] == "failed" for t in body["items"])


def test_list_transactions_filters_by_gateway_and_failure_code(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions",
                   params={"gateway": "razorpay", "failure_code": "insufficient_funds"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["external_id"] == "tx-3"


def test_list_transactions_pagination(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions", params={"limit": 2, "offset": 0})
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    first = [t["id"] for t in body["items"]]

    resp2 = api.get("/api/v1/transactions", params={"limit": 2, "offset": 2})
    body2 = resp2.json()
    assert len(body2["items"]) == 1
    second = [t["id"] for t in body2["items"]]
    # no overlap across pages (ordering by id desc)
    assert not set(first) & set(second)


# ---------------------------------------------------------------------------
# Transaction detail
# ---------------------------------------------------------------------------


def test_transaction_detail_includes_nested_records(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    tx_id = session.query(Transaction).filter_by(external_id="tx-1").one().id
    resp = api.get(f"/api/v1/transactions/{tx_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_id"] == "tx-1"
    assert body["status"] == "failed"
    assert body["amount"] == "100.00"
    # nested references
    assert body["customer"]["name"] == "Jane Doe"
    assert body["merchant"]["name"] == "Acme Corp"
    # persisted decisions + attempts
    assert len(body["decisions"]) == 1
    assert body["decisions"][0]["action"] == "RETRY_NOW"
    assert len(body["attempts"]) == 1
    assert body["attempts"][0]["status"] == "recovered"
    # audit logs (transaction + none-scoped) are attached to the detail
    assert len(body["audit_logs"]) == 1
    assert body["audit_logs"][0]["action"] == "recovery.evaluate:ALLOW"


def test_transaction_detail_missing_404(api):
    resp = api.get("/api/v1/transactions/999999")
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_summary_empty_db(api):
    resp = api.get("/api/v1/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transactions"] == 0
    assert body["total_recovery_attempts"] == 0
    assert body["recovery_decisions_total"] == 0
    assert body["failed_amount"] == "0.00"
    assert body["recovered_amount"] == "0.00"


def test_summary_metrics_calculated(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/summary")
    assert resp.status_code == 200
    body = resp.json()
    # transaction status axis
    assert body["total_transactions"] == 3
    assert body["transactions_by_status"]["failed"] == 2
    assert body["transactions_by_status"]["recovered"] == 1
    assert body["failed_amount"] == "300.00"
    assert body["recovered_amount"] == "50.00"
    assert body["total_amount"] == "350.00"
    # recovery attempt status axis (distinct from transaction status)
    assert body["total_recovery_attempts"] == 1
    assert body["recovery_attempts_by_status"]["recovered"] == 1
    # recovery decision outcome axis (distinct again)
    assert body["recovery_decisions_total"] == 2
    assert body["recovery_decisions_by_outcome"]["authorized"] == 1
    assert body["recovery_decisions_by_outcome"]["blocked"] == 1
    assert body["recovery_decisions_by_action"]["RETRY_NOW"] == 1
    assert body["recovery_decisions_by_action"]["STOP"] == 1


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_audit_listing(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/audit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    item = body["items"][0]
    for key in ("id", "transaction_id", "transaction_external_id", "actor",
                "action", "detail", "occurred_at"):
        assert key in item
    # structured detail parsed from stored JSON
    assert isinstance(item["detail"], dict)
    # transaction reference resolved where available
    system = [a for a in body["items"] if a["transaction_id"] is None]
    assert system and system[0]["transaction_external_id"] is None


def test_audit_filter_by_transaction(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    tx_id = session.query(Transaction).filter_by(external_id="tx-1").one().id
    resp = api.get("/api/v1/audit", params={"transaction_id": tx_id})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["transaction_id"] == tx_id


def test_audit_pagination(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/audit", params={"limit": 1, "offset": 0})
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1


# ---------------------------------------------------------------------------
# Read-only enforcement
# ---------------------------------------------------------------------------


def test_read_endpoints_do_not_mutate_database(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    before = _snapshot(session)

    tx_id = session.query(Transaction).filter_by(external_id="tx-1").one().id
    api.get("/api/v1/transactions")
    api.get("/api/v1/transactions", params={"status": "failed"})
    api.get(f"/api/v1/transactions/{tx_id}")
    api.get("/api/v1/summary")
    api.get("/api/v1/audit")
    api.get("/api/v1/audit", params={"transaction_id": tx_id})

    after = _snapshot(session)
    assert after == before
    # transaction state untouched: still 'failed'
    tx = session.get(Transaction, tx_id)
    assert tx.status == "failed"
