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

from razor_recover.api import dependencies
from razor_recover.core.database import Base
from razor_recover.db.models.audit import AuditLog
from razor_recover.db.models.customer import Customer
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.merchant import Merchant
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction
from razor_recover.main import create_app


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
                detail=(
                    '{"policy_decision": "ALLOW", '
                    '"execution_status": "recovered", '
                    '"llm_requested_action": "RETRY_NOW", '
                    '"recovery_probability": 0.72, '
                    '"rule_results": [{"rule": "action_allowlist", '
                    '"passed": true, "disposition": "pass"}]}'
                ),
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


def _seed_dated(session: Session):
    """Seed transactions with controlled attempted_at values for date-range tests."""
    merchant = Merchant(external_id="m-2", name="Acme Corp", industry="retail")
    customer = Customer(external_id="c-2", name="Jane Doe", email="jane@example.com")
    session.add_all([merchant, customer])
    session.flush()
    dated = [
        ("s-tx-1", datetime(2026, 1, 10, 9, 30, tzinfo=timezone.utc)),
        ("s-tx-2", datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)),
        ("s-tx-3", datetime(2026, 3, 10, 18, 45, tzinfo=timezone.utc)),
    ]
    session.add_all([
        Transaction(
            external_id=ext, created_at=created_at,
            customer_id=customer.id, merchant_id=merchant.id,
            amount=Decimal("25.00"), currency="USD", status="failed",
            failure_code="card_declined", failure_reason="declined",
            payment_method="card", gateway="stripe", attempt_number=1,
            attempted_at=created_at,
        )
        for ext, created_at in dated
    ])
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
        from razor_recover.services.read.dashboard import DashboardReadService
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


def test_list_transactions_exposes_latest_recovery_state(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions")
    body = resp.json()
    rows = {t["external_id"]: t for t in body["items"]}

    # tx-1 has a decision and an attempt
    tx1 = rows["tx-1"]
    assert tx1["latest_decision"]["action"] == "RETRY_NOW"
    assert tx1["latest_decision"]["outcome"] == "authorized"
    assert tx1["latest_decision"]["risk_score"] == "0.4000"
    assert tx1["latest_attempt"]["status"] == "recovered"
    assert tx1["latest_attempt"]["attempt_type"] == "RETRY_NOW"

    # tx-3 has only a decision (never executed); tx-2 has nothing
    tx3 = rows["tx-3"]
    assert tx3["latest_decision"]["action"] == "STOP"
    assert tx3["latest_decision"]["outcome"] == "blocked"
    assert tx3["latest_attempt"] is None
    assert rows["tx-2"]["latest_decision"] is None
    assert rows["tx-2"]["latest_attempt"] is None


def test_list_transactions_empty_recovery_state(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session, decisions=False, attempts=False, audits=False)
    resp = api.get("/api/v1/transactions")
    body = resp.json()
    assert all(t["latest_decision"] is None for t in body["items"])
    assert all(t["latest_attempt"] is None for t in body["items"])


def test_list_transactions_search_by_external_id(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions", params={"search": "tx-1"})
    body = resp.json()
    assert body["total"] == 1
    assert [t["external_id"] for t in body["items"]] == ["tx-1"]

    resp = api.get("/api/v1/transactions", params={"search": "no-such-txn"})
    assert resp.json()["total"] == 0


def test_list_transactions_search_by_customer_external_id(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions", params={"search": "c-1"})
    body = resp.json()
    assert body["total"] == 3
    assert all(t["customer_external_id"] == "c-1" for t in body["items"])


def test_list_transactions_search_partial_and_case_insensitive(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)
    resp = api.get("/api/v1/transactions", params={"search": "TX-"})
    body = resp.json()
    assert body["total"] == 3
    # search composes with other filters and respects pagination totals
    resp = api.get("/api/v1/transactions",
                   params={"search": "tx", "status": "failed", "limit": 2})
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert resp.json()  # JSON parseable


def test_list_transactions_attempted_date_range(api):
    session = api._session  # type: ignore[attr-defined]
    _seed_dated(session)

    jan = api.get("/api/v1/transactions",
                  params={"attempted_from": "2026-01-01", "attempted_to": "2026-01-31"})
    assert [t["external_id"] for t in jan.json()["items"]] == ["s-tx-1"]
    assert jan.json()["total"] == 1

    single_day = api.get("/api/v1/transactions",
                         params={"attempted_from": "2026-02-10",
                                 "attempted_to": "2026-02-10"})
    assert [t["external_id"] for t in single_day.json()["items"]] == ["s-tx-2"]
    assert single_day.json()["total"] == 1

    open_ended = api.get("/api/v1/transactions",
                         params={"attempted_from": "2026-03-01"})
    assert [t["external_id"] for t in open_ended.json()["items"]] == ["s-tx-3"]
    assert open_ended.json()["total"] == 1

    all_dates = api.get("/api/v1/transactions",
                        params={"attempted_to": "2026-04-01"})
    assert all_dates.json()["total"] == 3


def test_list_transactions_attempted_date_range_empty(api):
    session = api._session  # type: ignore[attr-defined]
    _seed_dated(session)

    no_hits = api.get("/api/v1/transactions",
                      params={"attempted_from": "2025-12-31",
                              "attempted_to": "2025-12-31"})
    assert no_hits.status_code == 200
    assert no_hits.json()["total"] == 0
    assert no_hits.json()["items"] == []


def test_list_transactions_attempted_date_range_with_pagination(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)

    resp = api.get("/api/v1/transactions",
                   params={"attempted_from": "2026-01-01",
                           "attempted_to": "2026-03-31",
                           "limit": 1, "offset": 1})
    body = resp.json()
    assert body["total"] == 3          # three 2026 tx-1..3 attempted_at values
    assert len(body["items"]) == 1
    assert body["items"][0]["external_id"] == "tx-2"


def test_list_transactions_status_filter_unaffected_by_date_rename(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session)

    failed = api.get("/api/v1/transactions",
                     params={"status": "failed",
                             "attempted_from": "2026-01-01",
                             "attempted_to": "2026-03-31"})
    assert failed.json()["total"] == 2  # tx-1 and tx-3 are failed

    gateway_and_method = api.get("/api/v1/transactions",
                                 params={"gateway": "razorpay",
                                         "payment_method": "upi",
                                         "attempted_from": "2026-01-01",
                                         "attempted_to": "2026-03-31"})
    assert [t["external_id"] for t in gateway_and_method.json()["items"]] == ["tx-2"]

    search = api.get("/api/v1/transactions",
                     params={"search": "c-1",
                             "attempted_from": "2026-01-01",
                             "attempted_to": "2026-03-31"})
    assert search.json()["total"] == 3


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
    assert body["decisions"][0]["risk_score"] == "0.4000"
    assert len(body["attempts"]) == 1
    assert body["attempts"][0]["status"] == "recovered"
    # audit logs (transaction + none-scoped) are attached to the detail
    assert len(body["audit_logs"]) == 1
    assert body["audit_logs"][0]["action"] == "recovery.evaluate:ALLOW"
    # values lifted from the persisted evaluate audit detail
    assert body["recovery_probability"] == 0.72
    assert body["shield_rule_results"] == [
        {"rule": "action_allowlist", "passed": True, "disposition": "pass"}
    ]


def test_transaction_detail_missing_404(api):
    resp = api.get("/api/v1/transactions/999999")
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"]


def test_transaction_detail_no_evaluate_meta_is_null(api):
    session = api._session  # type: ignore[attr-defined]
    _seed(session, decisions=False, attempts=False, audits=False)
    tx_id = session.query(Transaction).filter_by(external_id="tx-1").one().id
    resp = api.get(f"/api/v1/transactions/{tx_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recovery_probability"] is None
    assert body["shield_rule_results"] is None
    assert body["latest_decision"] is None
    assert body["latest_attempt"] is None


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
    assert body["recovery_decisions_by_risk_bucket"] == {
        "low": 0, "medium": 0, "high": 0, "unknown": 0,
    }
    assert body["recovery_decisions_by_probability_bucket"] == {
        "0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0, "unknown": 0,
    }


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
    # risk buckets computed from persisted decision risk scores
    assert body["recovery_decisions_by_risk_bucket"]["medium"] == 1  # 0.4
    assert body["recovery_decisions_by_risk_bucket"]["high"] == 1    # 0.9
    assert body["recovery_decisions_by_risk_bucket"]["low"] == 0
    assert body["recovery_decisions_by_risk_bucket"]["unknown"] == 0
    # probability buckets computed from persisted evaluate audit details
    prob = body["recovery_decisions_by_probability_bucket"]
    assert prob["60-80"] == 1     # seeded recovery_probability 0.72
    assert sum(prob.values()) == 1  # only the one evaluate event counts
    assert prob["0-20"] == 0
    assert prob["20-40"] == 0
    assert prob["40-60"] == 0
    assert prob["80-100"] == 0
    assert prob["unknown"] == 0


def test_summary_probability_buckets_count(api):
    """Counting spans every evaluate event and only evaluate events."""
    session = api._session  # type: ignore[attr-defined]
    _seed(session, audits=False)
    tx1 = session.query(Transaction).filter_by(external_id="tx-1").one()
    tx2 = session.query(Transaction).filter_by(external_id="tx-2").one()
    tx3 = session.query(Transaction).filter_by(external_id="tx-3").one()
    session.add_all([
        AuditLog(
            transaction_id=tx1.id, actor="recovery.workflow",
            action="recovery.evaluate:ALLOW",
            detail='{"recovery_probability": 0.05, "policy_decision": "ALLOW"}',
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        AuditLog(
            transaction_id=tx2.id, actor="recovery.workflow",
            action="recovery.evaluate:ALLOW",
            detail='{"recovery_probability": 0.35, "policy_decision": "ALLOW"}',
            occurred_at=datetime(2026, 2, 2, tzinfo=timezone.utc)),
        AuditLog(
            transaction_id=tx3.id, actor="recovery.workflow",
            action="recovery.evaluate:REVIEW",
            detail='{"recovery_probability": 0.55, "policy_decision": "REVIEW"}',
            occurred_at=datetime(2026, 3, 2, tzinfo=timezone.utc)),
        AuditLog(
            transaction_id=None, actor="system",
            action="system.startup",
            detail='{"booting": true, "recovery_probability": 0.99}',
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ])
    session.flush()
    resp = api.get("/api/v1/summary")
    assert resp.status_code == 200
    prob = resp.json()["recovery_decisions_by_probability_bucket"]
    assert prob == {
        "0-20": 1, "20-40": 1, "40-60": 1, "60-80": 0, "80-100": 0, "unknown": 0,
    }


def test_summary_probability_bucket_boundaries(api):
    """Bucket definition: inclusive lower bound, so values are counted once."""
    session = api._session  # type: ignore[attr-defined]
    _seed(session, audits=False)
    tx1 = session.query(Transaction).filter_by(external_id="tx-1").one()
    boundaries = [
        ("0.00", "0-20"),
        ("0.19", "0-20"),
        ("0.20", "20-40"),
        ("0.39", "20-40"),
        ("0.40", "40-60"),
        ("0.59", "40-60"),
        ("0.60", "60-80"),
        ("0.79", "60-80"),
        ("0.80", "80-100"),
        ("1.00", "80-100"),
    ]
    for i, (value, expected) in enumerate(boundaries):
        session.add(AuditLog(
            transaction_id=tx1.id, actor="recovery.workflow",
            action="recovery.evaluate:ALLOW",
            detail=f'{{"recovery_probability": {value}, "policy_decision": "ALLOW"}}',
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc)))
    session.flush()
    resp = api.get("/api/v1/summary")
    assert resp.status_code == 200
    prob = resp.json()["recovery_decisions_by_probability_bucket"]
    expected = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0, "unknown": 0}
    for value, bucket in boundaries:
        expected[bucket] += 1
    assert prob == expected


def test_summary_probability_null_and_malformed_are_unknown(api):
    """NULL / missing / unparseable probabilities count as unknown only."""
    session = api._session  # type: ignore[attr-defined]
    _seed(session, audits=False)
    tx1 = session.query(Transaction).filter_by(external_id="tx-1").one()
    tx2 = session.query(Transaction).filter_by(external_id="tx-2").one()
    session.add_all([
        AuditLog(
            transaction_id=tx1.id, actor="recovery.workflow",
            action="recovery.evaluate:ALLOW",
            detail='{"policy_decision": "ALLOW"}',
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        AuditLog(
            transaction_id=tx1.id, actor="recovery.workflow",
            action="recovery.evaluate:BLOCK",
            detail='{"recovery_probability": null, "policy_decision": "BLOCK"}',
            occurred_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
        AuditLog(
            transaction_id=tx2.id, actor="recovery.workflow",
            action="recovery.evaluate:ALLOW",
            detail='not-json',
            occurred_at=datetime(2026, 2, 2, tzinfo=timezone.utc)),
        AuditLog(
            transaction_id=None, actor="system",
            action="recovery.evaluate:ALLOW",
            detail=None,
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ])
    session.flush()
    resp = api.get("/api/v1/summary")
    assert resp.status_code == 200
    prob = resp.json()["recovery_decisions_by_probability_bucket"]
    assert prob["unknown"] == 4
    assert sum(prob.values()) == 4


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
                "action", "detail", "occurred_at",
                "llm_requested_action", "policy_decision", "execution_status"):
        assert key in item
    # structured detail parsed from stored JSON
    assert isinstance(item["detail"], dict)
    # flat views of the detail populated for evaluate events only
    evaluated = [a for a in body["items"] if a["transaction_id"] is not None]
    assert evaluated[0]["policy_decision"] == "ALLOW"
    assert evaluated[0]["execution_status"] == "recovered"
    assert evaluated[0]["llm_requested_action"] == "RETRY_NOW"
    # transaction reference resolved where available
    system = [a for a in body["items"] if a["transaction_id"] is None]
    assert system and system[0]["transaction_external_id"] is None
    assert system[0]["policy_decision"] is None
    assert not isinstance(body["items"][0]["detail"], str)


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
    api.get("/api/v1/transactions", params={"search": "tx", "attempted_from": "2026-01-01"})
    api.get(f"/api/v1/transactions/{tx_id}")
    api.get("/api/v1/summary")
    api.get("/api/v1/audit")
    api.get("/api/v1/audit", params={"transaction_id": tx_id})

    after = _snapshot(session)
    assert after == before
    # transaction state untouched: still 'failed'
    tx = session.get(Transaction, tx_id)
    assert tx.status == "failed"
