"""Typed Pydantic models representing generated synthetic records.

These are the dataset's canonical in-memory representation, decoupled from
both the ORM models and the API schemas. Persistence maps these onto the
SQLAlchemy models in a separate module.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SyntheticMerchant(BaseModel):
    external_id: str
    name: str
    industry: str
    status: str = "active"


class SyntheticCustomer(BaseModel):
    external_id: str
    name: str
    email: str
    status: str = "active"


class SyntheticHistory(BaseModel):
    """Derived customer payment behavior at the time of a transaction."""

    previous_failed_count: int = 0
    previous_successful_count: int = 0


class SyntheticTransaction(BaseModel):
    external_id: str
    customer_external_id: str
    merchant_external_id: str
    amount: Decimal = Field(gt=0)
    currency: str
    payment_method: str
    gateway: str
    timestamp: datetime
    failure_code: str
    failure_reason: str
    attempt_number: int = Field(ge=1)
    status: str
    history: SyntheticHistory


class SyntheticDecision(BaseModel):
    transaction_external_id: str
    action: str
    outcome: str
    risk_score: Decimal
    rationale: str
    decided_at: datetime


class SyntheticRecoveryAttempt(BaseModel):
    transaction_external_id: str
    status: str
    attempt_type: str
    started_at: datetime
    completed_at: datetime | None = None
    error_detail: str | None = None


class SyntheticDataset(BaseModel):
    """Container of all generated records with cross-reference integrity."""

    seed: int
    merchants: list[SyntheticMerchant]
    customers: list[SyntheticCustomer]
    transactions: list[SyntheticTransaction]
    decisions: list[SyntheticDecision]
    recovery_attempts: list[SyntheticRecoveryAttempt]

    @property
    def total_entities(self) -> int:
        """Total number of generated records across all entity types."""
        return (
            len(self.merchants)
            + len(self.customers)
            + len(self.transactions)
            + len(self.decisions)
            + len(self.recovery_attempts)
        )
