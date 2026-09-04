"""Read-only response schemas for the merchant dashboard.

These schemas surface persisted data only. They never trigger execution, never
mutate state, and never recompute ML/RAG/LLM results from scratch - they simply
serialize rows that were already persisted by the recovery workflow.

Money is represented as ``Decimal`` in list/detail payloads (matching existing
schemas) and as ``str`` for aggregate sums to avoid floating-point drift.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Transactions list
# ---------------------------------------------------------------------------


class TransactionListItem(BaseModel):
    """One row for the failed-payments dashboard table.

    Only non-sensitive customer/merchant references (external ids) are exposed;
    names, emails and phone numbers are intentionally excluded from the list.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    amount: Decimal
    currency: str
    status: str
    failure_code: str | None = None
    failure_reason: str | None = None
    payment_method: str | None = None
    gateway: str | None = None
    attempt_number: int = 1
    attempted_at: datetime | None = None
    created_at: datetime
    customer_id: int
    merchant_id: int
    customer_external_id: str | None = None
    merchant_external_id: str | None = None

    # Latest persisted recovery state for the row (None when the transaction
    # has never passed through the recovery workflow).
    latest_decision: RecoveryDecisionSummary | None = None
    latest_attempt: RecoveryAttemptSummary | None = None


class TransactionListResponse(BaseModel):
    """Paginated list of transactions with total count for the UI."""

    items: list[TransactionListItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Transaction detail
# ---------------------------------------------------------------------------


class CustomerReference(BaseModel):
    """Non-sensitive customer reference for a transaction detail page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    email: str | None = None
    status: str = "active"


class MerchantReference(BaseModel):
    """Non-sensitive merchant reference for a transaction detail page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    industry: str | None = None
    status: str = "active"


class RecoveryDecisionRead(BaseModel):
    """A persisted ML+RAG+LLM+shield decision (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    action: str
    outcome: str
    risk_score: Decimal | None = None
    policy_version: int | None = None
    rationale: str | None = None
    decided_at: datetime
    created_at: datetime


class RecoveryAttemptRead(BaseModel):
    """A persisted recovery attempt / execution record (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    decision_id: int | None = None
    status: str
    attempt_type: str
    error_detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class RecoveryDecisionSummary(BaseModel):
    """Compact view of the most recent decision for a list row (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    action: str
    outcome: str
    risk_score: Decimal | None = None
    rationale: str | None = None
    decided_at: datetime


class RecoveryAttemptSummary(BaseModel):
    """Compact view of the most recent attempt for a list row (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    attempt_type: str
    error_detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ShieldRuleResult(BaseModel):
    """One persisted shield rule result from an evaluate audit detail."""

    rule: str
    passed: bool
    disposition: str | None = None


class TransactionDetail(TransactionListItem):
    """Complete persisted view for the transaction-details screen.

    Nested related records (customer, merchant, decisions, attempts, audit
    logs) are included. Nothing here is recomputed.
    """

    customer: CustomerReference | None = None
    merchant: MerchantReference | None = None
    decisions: list[RecoveryDecisionRead] = Field(default_factory=list)
    attempts: list[RecoveryAttemptRead] = Field(default_factory=list)
    audit_logs: list[AuditLogItem] = Field(default_factory=list)

    # Values lifted from the most recent persisted evaluate audit detail.
    # Both are None when no evaluate has run for this transaction.
    recovery_probability: float | None = None
    shield_rule_results: list[ShieldRuleResult] | None = None


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class SummaryResponse(BaseModel):
    """Dashboard summary derived only from persisted data.

    The three distinct lifecycles are reported separately:

    * ``transactions_by_status`` - transaction.status
    * ``recovery_attempts_by_status`` - recovery_attempt.status
    * ``recovery_decisions`` - recovery_decision.outcome / action
    """

    total_transactions: int
    transactions_by_status: dict[str, int]

    total_recovery_attempts: int
    recovery_attempts_by_status: dict[str, int]

    recovery_decisions_total: int
    recovery_decisions_by_outcome: dict[str, int]
    recovery_decisions_by_action: dict[str, int]

    # Risk buckets computed from persisted decision risk scores
    # (low < 0.33, medium < 0.66, high >= 0.66, unknown = NULL).
    recovery_decisions_by_risk_bucket: dict[str, int] = Field(default_factory=dict)

    # Monetary aggregates across transactions (as strings to preserve precision).
    failed_amount: str
    recovered_amount: str
    total_amount: str


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class AuditLogItem(BaseModel):
    """One persisted audit event (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int | None = None
    transaction_external_id: str | None = None
    actor: str | None = None
    action: str
    detail: dict | None = None
    occurred_at: datetime
    created_at: datetime

    # First-class views of the persisted detail JSON so the frontend does not
    # need to dig through the raw dict. All are None when not applicable.
    llm_requested_action: str | None = None
    policy_decision: str | None = None
    execution_status: str | None = None


class AuditListResponse(BaseModel):
    """Paginated audit log list."""

    items: list[AuditLogItem]
    total: int
    limit: int
    offset: int


__all__ = [
    "AuditListResponse",
    "AuditLogItem",
    "CustomerReference",
    "MerchantReference",
    "RecoveryAttemptRead",
    "RecoveryAttemptSummary",
    "RecoveryDecisionRead",
    "RecoveryDecisionSummary",
    "ShieldRuleResult",
    "SummaryResponse",
    "TransactionDetail",
    "TransactionListItem",
    "TransactionListResponse",
]
