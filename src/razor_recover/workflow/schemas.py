"""Request/response schemas for the recovery evaluation workflow.

The API only exposes these shape-safe models - no business logic lives here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    """Input for the recovery evaluate endpoint."""

    transaction_id: int = Field(gt=0)


class EvaluateResponse(BaseModel):
    """Structured result of a full recovery evaluation/execution.

    Deliberately excludes secrets and unnecessary PII - only aggregate signals
    and decision metadata are surfaced.
    """

    transaction_id: int
    risk_score: float | None = None
    recovery_probability: float | None = None
    recommended_action: str | None = None      # what the LLM requested
    policy_decision: str                        # ALLOW / BLOCK / REVIEW
    authorized_action: str | None = None        # final_action that may run
    execution_status: str | None = None         # recovered/failed/scheduled/.../None
    recovery_status: str | None = None          # transaction status after
    rationale: str | None = None                # LLM rationale
    policy_reasons: list[str] = Field(default_factory=list)
    audit_id: int | None = None


__all__ = ["EvaluateRequest", "EvaluateResponse"]
