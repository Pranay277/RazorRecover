"""Structured input/output contracts for the AI decision agent.

The agent's job is to RECOMMEND a recovery action. It never executes anything.
All fields are typed and validated with Pydantic so malformed provider output
cannot propagate as a valid decision.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from src.razor_recover.brains.rag.schemas import RetrievalResult


class AllowedAction(str, Enum):
    """The only recovery actions the agent is allowed to RECOMMEND.

    These are recommendations - the Policy Engine decides whether any action is
    actually authorized, and the Execution layer performs it.
    """

    RETRY_NOW = "RETRY_NOW"
    DELAYED_RETRY = "DELAYED_RETRY"
    ALTERNATIVE_PAYMENT = "ALTERNATIVE_PAYMENT"
    CUSTOMER_NOTIFICATION = "CUSTOMER_NOTIFICATION"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    STOP = "STOP"


# ---------------------------------------------------------------------------
# Input context
# ---------------------------------------------------------------------------


class TransactionSnapshot(BaseModel):
    """Eval-time facts about the failed payment (no post-recovery fields)."""

    external_id: str
    amount: float = Field(ge=0)
    currency: str
    failure_code: str
    failure_reason: str = ""
    payment_method: str = ""
    gateway: str = ""
    attempt_number: int = Field(ge=1, default=1)


class CustomerSnapshot(BaseModel):
    """Customer/history context (optional - may be absent)."""

    external_id: str
    prior_successful_count: int = Field(ge=0, default=0)
    prior_failed_count: int = Field(ge=0, default=0)
    status: str = "active"


class MerchantSnapshot(BaseModel):
    """Merchant context (optional - may be absent)."""

    external_id: str
    name: str = ""
    industry: str = ""


class DecisionRequest(BaseModel):
    """All inputs the agent receives to produce one recommendation."""

    transaction: TransactionSnapshot
    customer: CustomerSnapshot | None = None
    merchant: MerchantSnapshot | None = None
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    recovery_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieved_context: RetrievalResult | None = None
    request_id: str | None = None

    @field_validator("customer", "merchant", "retrieved_context", mode="before")
    @classmethod
    def _ignore_none_objects(cls, v):
        return v  # pass-through; None handled naturally


# ---------------------------------------------------------------------------
# Output decision
# ---------------------------------------------------------------------------


class AgentDecision(BaseModel):
    """A structured recovery RECOMMENDATION produced by the agent."""

    transaction_external_id: str
    action: AllowedAction
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    requires_policy_review: bool = False

    # ML signals as evidence (mirror what was supplied; optional).
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    recovery_probability: float | None = Field(default=None, ge=0.0, le=1.0)

    # Context the agent actually used, for auditability.
    supporting_context: list[str] = Field(default_factory=list)
    knowledge_references: list[str] = Field(default_factory=list)
    policy_references: list[str] = Field(default_factory=list)

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, v):
        if isinstance(v, str):
            v = v.strip().upper()
        return v
