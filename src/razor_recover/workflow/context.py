"""Adapts database records into the input contracts each pipeline layer needs.

Keeps the workflow decoupled: DB models are mapped into the ML feature source,
the LLM ``DecisionRequest``, and the shield ``EvaluationContext``. Adapters only
read - they never mutate or decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from src.razor_recover.brains.llm.schemas import (
    AgentDecision,
    CustomerSnapshot,
    DecisionRequest,
    MerchantSnapshot,
    TransactionSnapshot,
)
from src.razor_recover.db.models.merchant import Merchant
from src.razor_recover.db.models.transaction import Transaction
from src.razor_recover.shield.schemas import EvaluationContext, MerchantPolicy

SUCCESS_STATUSES = {"recovered", "succeed", "success", "completed"}
FAILED_STATUSES = {"failed", "declined", "blocked"}


# ---------------------------------------------------------------------------
# ML feature source adapter
# ---------------------------------------------------------------------------


@dataclass
class _History:
    previous_failed_count: int = 0
    previous_successful_count: int = 0


@dataclass
class FeatureSource:
    """Duck-typed object matching the ML feature builder's expected shape."""

    external_id: str
    merchant_external_id: str
    amount: Decimal
    currency: str
    payment_method: str
    gateway: str
    failure_code: str
    failure_reason: str = ""
    attempt_number: int = 1
    history: _History = field(default_factory=_History)


def build_feature_source(transaction: Transaction) -> FeatureSource:
    """Map a DB Transaction (and its customer) into an ML feature source."""
    history = _History()
    customer = transaction.customer
    if customer is not None:
        for prior in getattr(customer, "transactions", []) or []:
            if prior.id == transaction.id:
                continue
            status = (prior.status or "").lower()
            if status in SUCCESS_STATUSES:
                history.previous_successful_count += 1
            elif status in FAILED_STATUSES:
                history.previous_failed_count += 1

    return FeatureSource(
        external_id=transaction.external_id,
        merchant_external_id=transaction.merchant.external_id
        if transaction.merchant is not None
        else "unknown",
        amount=transaction.amount or Decimal("0"),
        currency=transaction.currency or "USD",
        payment_method=transaction.payment_method or "card",
        gateway=transaction.gateway or "unknown",
        failure_code=transaction.failure_code or "unknown",
        failure_reason=transaction.failure_reason or "",
        attempt_number=transaction.attempt_number or 1,
        history=history,
    )


# ---------------------------------------------------------------------------
# LLM DecisionRequest
# ---------------------------------------------------------------------------


def build_decision_request(
    transaction: Transaction,
    risk_score: float | None,
    recovery_probability: float | None,
    retrieved_context,
    request_id: str | None = None,
) -> DecisionRequest:
    """Map DB records + ML signals + RAG context into an LLM decision request."""
    merchant_name = transaction.merchant.name if transaction.merchant else ""
    merchant_industry = transaction.merchant.industry if transaction.merchant else ""
    merchant_ext = (
        transaction.merchant.external_id if transaction.merchant is not None else ""
    )

    customer = transaction.customer
    return DecisionRequest(
        transaction=TransactionSnapshot(
            external_id=transaction.external_id,
            amount=float(transaction.amount or 0),
            currency=transaction.currency or "USD",
            failure_code=transaction.failure_code or "unknown",
            failure_reason=transaction.failure_reason or "",
            payment_method=transaction.payment_method or "",
            gateway=transaction.gateway or "",
            attempt_number=transaction.attempt_number or 1,
        ),
        customer=(
            CustomerSnapshot(
                external_id=customer.external_id,
                prior_successful_count=len(
                    [t for t in (getattr(customer, "transactions", []) or [])
                     if (t.status or "").lower() in SUCCESS_STATUSES]
                ),
                prior_failed_count=len(
                    [t for t in (getattr(customer, "transactions", []) or [])
                     if (t.status or "").lower() in FAILED_STATUSES]
                ),
                status=customer.status or "active",
            )
            if customer is not None
            else None
        ),
        merchant=(
            MerchantSnapshot(
                external_id=merchant_ext,
                name=merchant_name,
                industry=merchant_industry or "",
            )
            if transaction.merchant is not None
            else None
        ),
        risk_score=risk_score,
        recovery_probability=recovery_probability,
        retrieved_context=retrieved_context,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Shield EvaluationContext
# ---------------------------------------------------------------------------


def build_shield_context(
    transaction: Transaction,
    agent_decision: AgentDecision | None,
    merchant_policy: MerchantPolicy | None,
    risk_score: float | None,
    recovery_probability: float | None,
    retry_attempts: int | None,
    history_available: bool,
) -> EvaluationContext:
    """Map pipeline state into the policy engine's evaluation context."""
    return EvaluationContext(
        requested_action=agent_decision.action if agent_decision else None,
        agent_decision=agent_decision,
        transaction=TransactionSnapshot(
            external_id=transaction.external_id,
            amount=float(transaction.amount or 0),
            currency=transaction.currency or "USD",
            failure_code=transaction.failure_code or "unknown",
            failure_reason=transaction.failure_reason or "",
            payment_method=transaction.payment_method or "",
            gateway=transaction.gateway or "",
            attempt_number=transaction.attempt_number or 1,
        ),
        merchant_policy=merchant_policy,
        risk_score=risk_score,
        recovery_probability=recovery_probability,
        retry_attempts=retry_attempts,
        history_available=history_available,
    )


__all__ = [
    "FeatureSource",
    "build_feature_source",
    "build_decision_request",
    "build_shield_context",
]
