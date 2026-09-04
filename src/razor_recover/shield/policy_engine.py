"""Policy / Safety Engine - the deterministic safety boundary.

The engine receives transaction context, merchant policy, ML signals and the
LLM's :class:`AgentDecision` and authorizes directly with no LLM involvement.
It returns an auditable :class:`PolicyDecision`. It never executes retries,
notifications, payments or any state mutation - that is Phase 7's job.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

from src.razor_recover.brains.llm.schemas import AllowedAction
from src.razor_recover.core.logger import get_logger
from src.razor_recover.shield.exceptions import (
    InvalidPolicyContextError,
    PolicyEvaluationError,
    UnknownRuleError,
)
from src.razor_recover.shield.evaluator import evaluate_rules
from src.razor_recover.shield.rules import PolicyRule, default_rule_set
from src.razor_recover.shield.schemas import (
    EvaluationContext,
    PolicyDecision,
    PolicyDecisionType,
    ShieldConfig,
)

logger = get_logger("shield.policy_engine")


class PolicyEngine:
    """Deterministic rule aggregation engine (ALLOW / BLOCK / REVIEW)."""

    def __init__(
        self,
        config: ShieldConfig | None = None,
        rules: Sequence[PolicyRule] | None = None,
    ) -> None:
        self.config = config or ShieldConfig()
        self.rules = list(rules) if rules is not None else default_rule_set(self.config)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_settings(cls, settings=None) -> "PolicyEngine":
        """Build an engine from the settings system (demo defaults)."""
        return cls(config=ShieldConfig.from_settings(settings))

    @property
    def rule_names(self) -> list[str]:
        return [getattr(r, "name", type(r).__name__) for r in self.rules]

    # -- public API ---------------------------------------------------------

    def evaluate(self, context: EvaluationContext) -> PolicyDecision:
        """Evaluate a context and return an auditable decision (never executes).

        Any unexpected failure during evaluation results in a BLOCK decision
        (fail closed), so an error can never accidentally authorize an action.
        """
        if not isinstance(context, EvaluationContext):
            raise InvalidPolicyContextError(
                "evaluate() requires an EvaluationContext instance."
            )

        requested = self._resolve_action(context)
        try:
            outcome = evaluate_rules(context, self.rules)
        except Exception as exc:  # noqa: BLE001 - fail closed
            logger.exception("Policy evaluation failed")
            outcome = None
            fail_reason = f"Policy evaluation exception - failing closed: {exc}"

        if outcome is None:
            return self._decision(
                PolicyDecisionType.BLOCK,
                requested,
                final_action=None,
                reasons=[fail_reason],
                context=context,
                error_result=None,
            )

        # Only ALLOW authorizes the action to actually run.
        final_action = requested if outcome.decision == PolicyDecisionType.ALLOW else None
        return self._decision(
            outcome.decision,
            requested,
            final_action=final_action,
            reasons=outcome.reasons,
            context=context,
            rule_results=outcome.rule_results,
        )

    def run_rule(self, context: EvaluationContext, rule_name: str):
        """Evaluate a single named rule (useful for diagnostics)."""
        for rule in self.rules:
            if getattr(rule, "name", None) == rule_name:
                return rule.evaluate(context)
        raise UnknownRuleError(f"No rule named {rule_name!r}.")

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _resolve_action(context: EvaluationContext) -> str | None:
        action = context.requested_action
        if action is None and context.agent_decision is not None:
            action = context.agent_decision.action
        if isinstance(action, AllowedAction):
            return action.value
        return None

    def _decision(
        self,
        decision: PolicyDecisionType,
        requested: str | None,
        final_action: str | None,
        reasons: list[str],
        context: EvaluationContext,
        rule_results=None,
        error_result=None,
    ) -> PolicyDecision:
        version = self.config.policy_version
        if context.merchant_policy is not None and context.merchant_policy.policy_version:
            version = context.merchant_policy.policy_version
        return PolicyDecision(
            decision=decision,
            requested_action=requested,
            final_action=final_action,
            rule_results=list(rule_results) if rule_results else [],
            reasons=reasons,
            risk_score=context.risk_score,
            recovery_probability=context.recovery_probability,
            policy_version=version,
            evaluated_at=datetime.now(timezone.utc),
        )


__all__ = ["PolicyEngine"]
