"""Typed contracts for the Policy / Safety Engine (shield).

These are pure data models - no decision logic lives here. The engine consumes
an :class:`EvaluationContext` and returns a :class:`PolicyDecision`. Per-merchant
policies and engine-level configuration are provided as value objects so the
engine stays independent of FastAPI and the database.

The engine never asks the LLM whether an action is safe; it only uses the LLM's
``AgentDecision`` (an action *recommendation*) as one input among several.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from razor_recover.brains.llm.schemas import (
    AgentDecision,
    AllowedAction,
    TransactionSnapshot,
)


class PolicyDecisionType(str, Enum):
    """Authoritative outcome produced by the policy engine."""

    ALLOW = "ALLOW"   # The recommended action is authorized to proceed.
    BLOCK = "BLOCK"   # The recommended action is rejected; nothing runs.
    REVIEW = "REVIEW"  # Do not auto-execute; escalate to manual review.


class RuleDisposition(str, Enum):
    """The safety effect of a single failed rule."""

    BLOCK = "BLOCK"      # This failure forbids the action.
    REVIEW = "REVIEW"    # This failure forbids auto-execution but permits review.


class RuleResult(BaseModel):
    """Outcome of evaluating a single policy rule.

    ``passed`` is True when the rule found no concern. When False,
    ``disposition`` says whether the concern blocks or escalates to review.
    """

    rule_name: str
    passed: bool
    disposition: RuleDisposition | None = None
    reason: str = ""
    severity: str = "info"

    @classmethod
    def pass_rule(cls, rule_name: str, reason: str = "") -> "RuleResult":
        return cls(rule_name=rule_name, passed=True, reason=reason)

    @classmethod
    def fail_rule(
        cls,
        rule_name: str,
        disposition: RuleDisposition,
        reason: str,
        severity: str,
    ) -> "RuleResult":
        return cls(rule_name=rule_name, passed=False, disposition=disposition,
                   reason=reason, severity=severity)


class ShieldConfig(BaseModel):
    """Engine-level configuration with documented demo/synthetic default values.

    These are RazorRecover demo policy values, NOT real Razorpay limits. They can
    be overridden through the settings system (``policy_*`` env vars) or by
    providing a richer :class:`MerchantPolicy` in the context.
    """

    policy_version: int = 1
    block_on_unknown_action: bool = True
    block_on_missing_transaction: bool = True
    review_on_missing_policy: bool = True
    force_review_on_high_value: bool = True

    # Demo defaults used when a merchant policy does not supply a value.
    default_max_retries: int = 3
    default_max_risk_score: float = 0.70
    default_min_recovery_probability: float = 0.30
    default_high_value_threshold: float = 10_000.0

    @classmethod
    def from_settings(cls, settings=None) -> "ShieldConfig":
        """Build engine config from the settings system, falling back to
        defaults for any unset ``policy_*`` field."""
        if settings is None:
            return cls()
        values = {
            "policy_version": getattr(settings, "policy_version", None),
            "default_max_retries": getattr(settings, "policy_default_max_retries", None),
            "default_max_risk_score": getattr(settings, "policy_default_max_risk_score", None),
            "default_min_recovery_probability": getattr(
                settings, "policy_default_min_recovery_probability", None
            ),
            "default_high_value_threshold": getattr(
                settings, "policy_default_high_value_threshold", None
            ),
        }
        values = {k: v for k, v in values.items() if v is not None}
        return cls(**values)


class MerchantPolicy(BaseModel):
    """Per-merchant policy controls consumed by the engine.

    ``None`` numeric fields fall back to :class:`ShieldConfig` demo defaults.
    This is the structured, deterministic representation of a merchant's policy
    (distinct from the generic expression-based ``Policy`` ORM row).
    """

    model_config = ConfigDict(extra="forbid")

    merchant_external_id: str
    retry_enabled: bool = True
    max_retries: int | None = Field(default=None, ge=1)
    max_risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    min_recovery_probability: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    high_value_threshold: float | None = Field(default=None, ge=0.0)
    customer_notifications_enabled: bool = True
    disallowed_actions: list[AllowedAction] = Field(default_factory=list)
    policy_version: int | None = None


class EvaluationContext(BaseModel):
    """All inputs the policy engine needs to authorize one recommendation.

    Every field is optional so the engine can fail closed on missing data
    rather than crashing.
    """

    requested_action: AllowedAction | None = None
    agent_decision: AgentDecision | None = None
    transaction: TransactionSnapshot | None = None
    merchant_policy: MerchantPolicy | None = None
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    recovery_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    retry_attempts: int | None = Field(default=None, ge=0)
    history_available: bool = True


class PolicyDecision(BaseModel):
    """The auditable, deterministic outcome of a policy evaluation.

    Contains everything Phase 7 needs to persist: the action the LLM requested,
    every rule result (pass/fail), the aggregated decision, reasons, and the
    policy version used.
    """

    decision: PolicyDecisionType
    requested_action: str | None = None
    final_action: str | None = None
    rule_results: list[RuleResult] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risk_score: float | None = None
    recovery_probability: float | None = None
    policy_version: int = 1
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def effective_policy_version(self) -> int:
        """Return the highest explicit policy version, else the recorded one."""
        return self.policy_version


__all__ = [
    "PolicyDecisionType",
    "RuleDisposition",
    "RuleResult",
    "ShieldConfig",
    "MerchantPolicy",
    "EvaluationContext",
    "PolicyDecision",
]
