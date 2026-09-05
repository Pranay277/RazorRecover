"""Unit tests for the execution layer (PERFORMS authorized actions).

Verifies the gateway abstraction, the ALLOW-only execution gate, outcome
mapping, and idempotency - all deterministic, no external services.
"""

import pytest

from razor_recover.brains.llm.schemas import AllowedAction
from razor_recover.db.models.customer import Customer
from razor_recover.db.models.merchant import Merchant
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction
from razor_recover.execution.exceptions import UnauthorizedExecutionError
from razor_recover.execution.gateway import MockPaymentGateway, create_payment_gateway
from razor_recover.execution.recovery_service import RecoveryService
from razor_recover.execution.retry_service import RetryService
from razor_recover.execution.schemas import ExecutionStatus, GatewayOutcome
from razor_recover.shield.schemas import PolicyDecision, PolicyDecisionType


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

def test_mock_gateway_default_success():
    gw = create_payment_gateway(provider="mock")
    res = gw.charge(10.0, "USD", "ref-1")
    assert res.outcome == GatewayOutcome.SUCCESS
    assert res.reference == "ref-1"


def test_mock_gateway_configurable_outcome():
    gw = MockPaymentGateway()
    gw.configure("ref-timeout", GatewayOutcome.TIMEOUT)
    gw.configure("ref-fail", "FAILED")
    assert gw.charge(1, "USD", "ref-timeout").outcome == GatewayOutcome.TIMEOUT
    assert gw.charge(1, "USD", "ref-fail").outcome == GatewayOutcome.FAILED
    # unmapped -> default success
    assert gw.charge(1, "USD", "other").outcome == GatewayOutcome.SUCCESS


def test_gateway_records_calls_not_external():
    gw = create_payment_gateway(provider="mock")
    gw.charge(10.0, "USD", "ref-a")
    assert len(gw.calls) == 1
    assert gw.calls[0]["reference"] == "ref-a"


# ---------------------------------------------------------------------------
# RecoveryService - ALLOW gate + outcome mapping + persistence
# ---------------------------------------------------------------------------

def _seed_transaction(session, status="failed") -> Transaction:
    merchant = Merchant(external_id="m-1", name="M", industry="retail", status="active")
    customer = Customer(external_id="c-1", name="C", email="c@example.com", status="active")
    session.add_all([merchant, customer])
    session.flush()
    tx = Transaction(
        external_id="tx-1",
        customer_id=customer.id,
        merchant_id=merchant.id,
        amount=100,
        currency="USD",
        status=status,
        failure_code="card_declined",
        failure_reason="declined",
        payment_method="card",
        gateway="stripe",
        attempt_number=1,
    )
    session.add(tx)
    session.flush()
    return tx


def _allow_decision(action="RETRY_NOW") -> PolicyDecision:
    return PolicyDecision(
        decision=PolicyDecisionType.ALLOW,
        requested_action=action,
        final_action=action,
    )


def test_retry_now_success_marks_recovered(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = create_payment_gateway(provider="mock")  # default SUCCESS
    svc = RecoveryService(retry_service=RetryService(gateway=gw))
    result = svc.execute(decision=_allow_decision(), session=sqlite_session, transaction=tx)
    sqlite_session.flush()
    assert result.status == ExecutionStatus.RECOVERED
    assert tx.status == "recovered"
    attempt = sqlite_session.query(RecoveryAttempt).one()
    assert attempt.attempt_type == "RETRY_NOW"
    assert attempt.status == "recovered"


def test_failed_gateway_does_not_mark_recovered(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway(default_outcome=GatewayOutcome.FAILED)
    svc = RecoveryService(retry_service=RetryService(gateway=gw))
    result = svc.execute(decision=_allow_decision(), session=sqlite_session, transaction=tx)
    sqlite_session.flush()
    assert result.status == ExecutionStatus.FAILED
    assert tx.status == "failed"  # never falsely mark recovered
    assert sqlite_session.query(RecoveryAttempt).one().status == "failed"


def test_timeout_gateway_records_timeout(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway(default_outcome=GatewayOutcome.TIMEOUT)
    svc = RecoveryService(retry_service=RetryService(gateway=gw))
    result = svc.execute(decision=_allow_decision(), session=sqlite_session, transaction=tx)
    sqlite_session.flush()
    assert result.status == ExecutionStatus.TIMEOUT
    assert tx.status == "failed"
    assert sqlite_session.query(RecoveryAttempt).one().status == "timeout"


def test_block_decision_never_executes(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway()
    svc = RecoveryService(retry_service=RetryService(gateway=gw))
    block = PolicyDecision(
        decision=PolicyDecisionType.BLOCK, requested_action="RETRY_NOW", final_action=None
    )
    with pytest.raises(UnauthorizedExecutionError):
        svc.execute(decision=block, session=sqlite_session, transaction=tx)
    assert len(gw.calls) == 0
    assert sqlite_session.query(RecoveryAttempt).count() == 0


def test_review_decision_never_executes(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway()
    svc = RecoveryService(retry_service=RetryService(gateway=gw))
    review = PolicyDecision(
        decision=PolicyDecisionType.REVIEW, requested_action="RETRY_NOW", final_action=None
    )
    with pytest.raises(UnauthorizedExecutionError):
        svc.execute(decision=review, session=sqlite_session, transaction=tx)
    assert len(gw.calls) == 0
    assert sqlite_session.query(RecoveryAttempt).count() == 0


def test_all_allow_decision_without_final_action_refused(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    svc = RecoveryService()
    decision = PolicyDecision(decision=PolicyDecisionType.ALLOW, requested_action="RETRY_NOW", final_action=None)
    with pytest.raises(UnauthorizedExecutionError):
        svc.execute(decision=decision, session=sqlite_session, transaction=tx)


def test_manual_review_stop_never_auto_executed(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    gw = MockPaymentGateway()
    svc = RecoveryService(retry_service=RetryService(gateway=gw))
    # Even if a decision somehow said ALLOW with MANUAL_REVIEW, execution must refuse.
    bad = PolicyDecision(decision=PolicyDecisionType.ALLOW,
                         requested_action="MANUAL_REVIEW", final_action="MANUAL_REVIEW")
    with pytest.raises(UnauthorizedExecutionError):
        svc.execute(decision=bad, session=sqlite_session, transaction=tx)
    assert len(gw.calls) == 0


def test_idempotency_skips_duplicate_in_flight(sqlite_session):
    tx = _seed_transaction(sqlite_session)
    svc = RecoveryService()
    # Pre-existing in-flight attempt
    sqlite_session.add(RecoveryAttempt(
        transaction_id=tx.id, attempt_type="RETRY_NOW", status="pending", started_at=tx.attempted_at
    ))
    sqlite_session.flush()
    result = svc.execute(decision=_allow_decision(), session=sqlite_session, transaction=tx)
    sqlite_session.flush()
    assert result.status == ExecutionStatus.SCHEDULED
    # Still exactly one attempt - no duplicate execution.
    assert sqlite_session.query(RecoveryAttempt).count() == 1
