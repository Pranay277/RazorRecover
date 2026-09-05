"""Unit tests for SQLAlchemy ORM models."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from razor_recover.db.models.audit import AuditLog
from razor_recover.db.models.customer import Customer
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.merchant import Merchant
from razor_recover.db.models.policy import Policy
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction


@pytest.fixture
def merchant_customer(postgres_session_isolated):
    suffix = datetime.now(timezone.utc).strftime("%f")
    merchant = Merchant(external_id=f"merchant-{suffix}", name="Merchant One")
    customer = Customer(external_id=f"customer-{suffix}", name="Customer One")
    postgres_session_isolated.add_all([merchant, customer])
    postgres_session_isolated.flush()
    return merchant, customer


def test_merchant_external_id_is_unique(postgres_session_isolated):
    suffix = datetime.now(timezone.utc).strftime("%f")
    postgres_session_isolated.add(Merchant(external_id=f"dup-{suffix}", name="First"))
    postgres_session_isolated.flush()

    postgres_session_isolated.add(Merchant(external_id=f"dup-{suffix}", name="Second"))
    with pytest.raises(IntegrityError):
        postgres_session_isolated.flush()
    postgres_session_isolated.rollback()


def test_policy_required_fields(postgres_session_isolated):
    suffix = datetime.now(timezone.utc).strftime("%f")
    policy = Policy(
        name=f"max-retry-{suffix}",
        expression="attempts < 3",
        enabled=True,
        priority=10,
    )
    postgres_session_isolated.add(policy)
    postgres_session_isolated.flush()

    loaded = postgres_session_isolated.get(Policy, policy.id)
    assert loaded.name == f"max-retry-{suffix}"
    assert loaded.enabled is True


def test_recovery_decision_links_transaction_and_policy(
    postgres_session_isolated, merchant_customer
):
    merchant, customer = merchant_customer
    suffix = datetime.now(timezone.utc).strftime("%f")
    transaction = Transaction(
        external_id=f"tx-decision-{suffix}",
        customer_id=customer.id,
        merchant_id=merchant.id,
        amount=Decimal("10.00"),
    )
    postgres_session_isolated.add(transaction)
    postgres_session_isolated.flush()

    policy = Policy(name=f"allow-retry-{suffix}", expression="true")
    postgres_session_isolated.add(policy)
    postgres_session_isolated.flush()

    decision = RecoveryDecision(
        transaction_id=transaction.id,
        action="retry",
        risk_score=Decimal("0.2500"),
        policy_id=policy.id,
        decided_at=datetime.now(timezone.utc),
    )
    postgres_session_isolated.add(decision)
    postgres_session_isolated.flush()

    loaded = postgres_session_isolated.get(RecoveryDecision, decision.id)
    assert loaded.transaction.external_id == f"tx-decision-{suffix}"
    assert loaded.policy.name == f"allow-retry-{suffix}"


def test_recovery_attempt_optional_decision(postgres_session_isolated, merchant_customer):
    merchant, customer = merchant_customer
    suffix = datetime.now(timezone.utc).strftime("%f")
    transaction = Transaction(
        external_id=f"tx-attempt-{suffix}",
        customer_id=customer.id,
        merchant_id=merchant.id,
        amount=Decimal("5.00"),
    )
    postgres_session_isolated.add(transaction)
    postgres_session_isolated.flush()

    attempt = RecoveryAttempt(
        transaction_id=transaction.id,
        attempt_type="card_retry",
        status="pending",
    )
    postgres_session_isolated.add(attempt)
    postgres_session_isolated.flush()

    loaded = postgres_session_isolated.get(RecoveryAttempt, attempt.id)
    assert loaded.decision is None
    assert loaded.transaction.external_id == f"tx-attempt-{suffix}"


def test_audit_log_can_exist_without_transaction(postgres_session_isolated):
    audit = AuditLog(
        action="system.startup",
        detail="service initialized",
        occurred_at=datetime.now(timezone.utc),
    )
    postgres_session_isolated.add(audit)
    postgres_session_isolated.flush()

    loaded = postgres_session_isolated.get(AuditLog, audit.id)
    assert loaded.transaction_id is None
    assert loaded.action == "system.startup"
