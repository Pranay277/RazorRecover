"""Deterministic, composable policy rules for the Safety Engine.

Each rule implements :meth:`evaluate(context) -> RuleResult` and is purely
deterministic: the same context always yields the same result, and no rule ever
consults the LLM. Rules are small and independent so future rules can be added
without rewriting the engine. Numeric thresholds come from
:class:`MerchantPolicy` (per merchant) or :class:`ShieldConfig` demo defaults.

Fail-closed behavior is documented per rule: when data that is *required* to
safely authorize an action is missing, the rule refuses to pass.
"""

from __future__ import annotations

from typing import Protocol

from razor_recover.brains.llm.schemas import AllowedAction
from razor_recover.shield.schemas import (
    EvaluationContext,
    MerchantPolicy,
    RuleDisposition,
    RuleResult,
    ShieldConfig,
)

RETRY_ACTIONS = {AllowedAction.RETRY_NOW, AllowedAction.DELAYED_RETRY}
RISK_SENSITIVE_ACTIONS = RETRY_ACTIONS | {AllowedAction.ALTERNATIVE_PAYMENT}
NEEDS_POLICY_ACTIONS = RISK_SENSITIVE_ACTIONS | {AllowedAction.CUSTOMER_NOTIFICATION}


class PolicyRule(Protocol):
    """Interface implemented by every policy rule."""

    name: str

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        """Evaluate the rule against a context; never raises."""


class RuleMixin:
    """Shared helpers for rules that read effective per-merchant values."""

    def __init__(self, config: ShieldConfig) -> None:
        self.config = config

    def _action(self, ctx: EvaluationContext) -> AllowedAction | None:
        if ctx.requested_action is not None:
            return ctx.requested_action
        if ctx.agent_decision is not None:
            action = ctx.agent_decision.action
            if isinstance(action, AllowedAction):
                return action
        return None

    @staticmethod
    def _policy(ctx: EvaluationContext) -> MerchantPolicy | None:
        return ctx.merchant_policy

    def _effective_max_retries(self, ctx: EvaluationContext) -> int:
        mp = ctx.merchant_policy
        if mp is not None and mp.max_retries is not None:
            return mp.max_retries
        return self.config.default_max_retries

    def _effective_max_risk(self, ctx: EvaluationContext) -> float:
        mp = ctx.merchant_policy
        if mp is not None and mp.max_risk_score is not None:
            return mp.max_risk_score
        return self.config.default_max_risk_score

    def _effective_min_recovery(self, ctx: EvaluationContext) -> float:
        mp = ctx.merchant_policy
        if mp is not None and mp.min_recovery_probability is not None:
            return mp.min_recovery_probability
        return self.config.default_min_recovery_probability

    def _effective_high_value(self, ctx: EvaluationContext) -> float:
        mp = ctx.merchant_policy
        if mp is not None and mp.high_value_threshold is not None:
            return mp.high_value_threshold
        return self.config.default_high_value_threshold


class ActionAllowlistRule(RuleMixin):
    """Reject requests with no action or an action outside the allowed set."""

    name = "action_allowlist"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action is None:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                "No recovery action was requested.", "error",
            )
        if not isinstance(action, AllowedAction) or action not in AllowedAction:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                f"Action {action!r} is not an allowed action.", "error",
            )
        return RuleResult.pass_rule(self.name, f"Action {action.value} is allowed.")


class StopActionRule(RuleMixin):
    """STOP is never authorized - it always blocks execution."""

    name = "stop_action"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action == AllowedAction.STOP:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                "STOP requested - do not execute any recovery action.", "error",
            )
        return RuleResult.pass_rule(self.name)


class ManualReviewActionRule(RuleMixin):
    """MANUAL_REVIEW must always be escalated to human review (never ALLOW)."""

    name = "manual_review_action"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action == AllowedAction.MANUAL_REVIEW:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                "Action requires manual review.", "warning",
            )
        return RuleResult.pass_rule(self.name)


class TransactionPresenceRule(RuleMixin):
    """A valid transaction is required; delete/fail closed if missing."""

    name = "transaction_presence"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        if context.transaction is None:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                "Transaction context is missing - cannot authorize an action.",
                "error",
            )
        return RuleResult.pass_rule(self.name)


class MerchantPolicyAvailabilityRule(RuleMixin):
    """Actions that depend on merchant policy fail closed if it is absent."""

    name = "merchant_policy_availability"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action in NEEDS_POLICY_ACTIONS and context.merchant_policy is None:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                f"Merchant policy missing for {action.value} - failing closed.",
                "warning",
            )
        return RuleResult.pass_rule(self.name)


class MerchantRestrictionRule(RuleMixin):
    """Block actions a merchant has explicitly disallowed."""

    name = "merchant_restriction"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        mp = context.merchant_policy
        if action is not None and mp is not None and action in mp.disallowed_actions:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                f"Merchant policy disallows {action.value}.", "error",
            )
        return RuleResult.pass_rule(self.name)


class RetryGuardsRule(RuleMixin):
    """Guards for retry actions: enabled toggle, attempt limits, history.

    - Retries disabled by the merchant -> BLOCK.
    - Retry history unavailable -> REVIEW (never auto-retry without history).
    - Attempt count at/over the limit -> BLOCK.
    """

    name = "retry_guards"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action not in RETRY_ACTIONS:
            return RuleResult.pass_rule(self.name)

        mp = context.merchant_policy
        if mp is not None and not mp.retry_enabled:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                "Merchant has disabled retries.", "error",
            )

        if not context.history_available or context.retry_attempts is None:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                "Retry history is unavailable - not auto-retrying.", "warning",
            )

        max_retries = self._effective_max_retries(context)
        if context.retry_attempts >= max_retries:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                f"Retry attempt limit reached ({context.retry_attempts} >= {max_retries}).",
                "error",
            )
        return RuleResult.pass_rule(self.name)


class RiskThresholdRule(RuleMixin):
    """Reject retries whose risk exceeds the merchant threshold.

    - Missing risk score -> REVIEW (fail closed; cannot confirm safety).
    - Retry: risk above threshold -> BLOCK.
    - Alternative payment: risk above threshold -> REVIEW (escalate, don't charge).
    """

    name = "risk_threshold"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action not in RISK_SENSITIVE_ACTIONS:
            return RuleResult.pass_rule(self.name)

        if context.risk_score is None:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                "Risk score is missing - failing closed.", "warning",
            )

        max_risk = self._effective_max_risk(context)
        if context.risk_score > max_risk:
            if action in RETRY_ACTIONS:
                return RuleResult.fail_rule(
                    self.name, RuleDisposition.BLOCK,
                    f"Risk score {context.risk_score:.2f} exceeds merchant retry "
                    f"threshold {max_risk:.2f}.", "error",
                )
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                f"Risk score {context.risk_score:.2f} exceeds threshold "
                f"{max_risk:.2f} - escalate before alternative payment.", "warning",
            )
        return RuleResult.pass_rule(self.name)


class RecoveryProbabilityRule(RuleMixin):
    """Escalate recovery attempts with low probability of success.

    - Missing recovery probability -> REVIEW (fail closed).
    - Below minimum -> REVIEW (low confidence; never auto-flag as safe).
    """

    name = "recovery_probability"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action not in RISK_SENSITIVE_ACTIONS:
            return RuleResult.pass_rule(self.name)

        if context.recovery_probability is None:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                "Recovery probability is missing - failing closed.", "warning",
            )

        min_recovery = self._effective_min_recovery(context)
        if context.recovery_probability < min_recovery:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                f"Recovery probability {context.recovery_probability:.2f} is below "
                f"minimum {min_recovery:.2f}.", "warning",
            )
        return RuleResult.pass_rule(self.name)


class HighValueReviewRule(RuleMixin):
    """Escalate recovery actions on high-value transactions."""

    name = "high_value_review"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action not in RISK_SENSITIVE_ACTIONS:
            return RuleResult.pass_rule(self.name)
        if context.transaction is None:
            return RuleResult.pass_rule(self.name)

        threshold = self._effective_high_value(context)
        if context.transaction.amount >= threshold:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                f"Transaction value {context.transaction.amount:.2f} meets/exceeds "
                f"high-value threshold {threshold:.2f}.", "warning",
            )
        return RuleResult.pass_rule(self.name)


class CustomerNotificationGuardRule(RuleMixin):
    """Respect communication restrictions for customer notifications."""

    name = "customer_notification"

    def evaluate(self, context: EvaluationContext) -> RuleResult:
        action = self._action(context)
        if action != AllowedAction.CUSTOMER_NOTIFICATION:
            return RuleResult.pass_rule(self.name)

        mp = context.merchant_policy
        if mp is None:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.REVIEW,
                "Merchant policy missing - cannot confirm notifications allowed.",
                "warning",
            )
        if not mp.customer_notifications_enabled:
            return RuleResult.fail_rule(
                self.name, RuleDisposition.BLOCK,
                "Merchant has disabled customer notifications.", "error",
            )
        return RuleResult.pass_rule(self.name)


def default_rule_set(config: ShieldConfig) -> list[PolicyRule]:
    """Build the standard, ordered set of policy rules for a given config."""
    return [
        ActionAllowlistRule(config),
        StopActionRule(config),
        ManualReviewActionRule(config),
        TransactionPresenceRule(config),
        MerchantPolicyAvailabilityRule(config),
        MerchantRestrictionRule(config),
        RetryGuardsRule(config),
        RiskThresholdRule(config),
        RecoveryProbabilityRule(config),
        HighValueReviewRule(config),
        CustomerNotificationGuardRule(config),
    ]


__all__ = [
    "PolicyRule",
    "ActionAllowlistRule",
    "StopActionRule",
    "ManualReviewActionRule",
    "TransactionPresenceRule",
    "MerchantPolicyAvailabilityRule",
    "MerchantRestrictionRule",
    "RetryGuardsRule",
    "RiskThresholdRule",
    "RecoveryProbabilityRule",
    "HighValueReviewRule",
    "CustomerNotificationGuardRule",
    "default_rule_set",
]
