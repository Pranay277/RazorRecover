"""Evaluation orchestration for the Safety Engine.

Runs an ordered list of rules against a context and aggregates their results
into a single :class:`PolicyDecisionType`. Aggregation is deterministic and
fail-closed:

- Any rule yielding a BLOCK -> final BLOCK.
- Else any rule yielding a REVIEW -> final REVIEW.
- Otherwise -> ALLOW.
- A rule that raises is treated as a BLOCK and recorded (fail closed).
"""

from __future__ import annotations

import logging
from typing import Sequence

from razor_recover.core.logger import get_logger
from razor_recover.shield.rules import PolicyRule
from razor_recover.shield.schemas import (
    EvaluationContext,
    PolicyDecisionType,
    RuleDisposition,
    RuleResult,
)

logger = get_logger("shield.evaluator")


class EvaluationOutcome:
    """Aggregated result of running the rule set."""

    def __init__(self) -> None:
        self.rule_results: list[RuleResult] = []
        self.reasons: list[str] = []

    @property
    def decision(self) -> PolicyDecisionType:
        if any(
            r.disposition == RuleDisposition.BLOCK
            for r in self.rule_results
        ):
            return PolicyDecisionType.BLOCK
        if any(
            r.disposition == RuleDisposition.REVIEW
            for r in self.rule_results
        ):
            return PolicyDecisionType.REVIEW
        return PolicyDecisionType.ALLOW


def evaluate_rules(
    context: EvaluationContext,
    rules: Sequence[PolicyRule],
) -> EvaluationOutcome:
    """Run every rule and aggregate a deterministic outcome (never raises)."""
    outcome = EvaluationOutcome()
    for rule in rules:
        try:
            result = rule.evaluate(context)
        except Exception as exc:  # noqa: BLE001 - fail closed on any rule error
            logger.exception("Rule %s raised while evaluating", getattr(rule, "name", "?"))
            result = RuleResult.fail_rule(
                getattr(rule, "name", "unknown"),
                RuleDisposition.BLOCK,
                f"Policy evaluation error - failing closed: {exc}",
                "error",
            )
        outcome.rule_results.append(result)
        if not result.passed:
            outcome.reasons.append(result.reason)
    return outcome


__all__ = ["EvaluationOutcome", "evaluate_rules"]
