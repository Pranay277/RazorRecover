"""Policy / Safety Engine - the deterministic safety boundary.

The LLM *recommends* an action; this package *authorizes* it. It is a pure,
deterministic component with no LLM, database, or HTTP coupling so it can run
independently and be reused across services.

Public API::

    engine = PolicyEngine.from_settings()
    decision = engine.evaluate(context)   # -> PolicyDecision (ALLOW/BLOCK/REVIEW)
"""

from razor_recover.shield.evaluator import EvaluationOutcome, evaluate_rules
from razor_recover.shield.exceptions import (
    InvalidPolicyContextError,
    PolicyError,
    PolicyEvaluationError,
    UnknownRuleError,
)
from razor_recover.shield.policy_engine import PolicyEngine
from razor_recover.shield.rules import (
    PolicyRule,
    default_rule_set,
)
from razor_recover.shield.schemas import (
    EvaluationContext,
    MerchantPolicy,
    PolicyDecision,
    PolicyDecisionType,
    RuleDisposition,
    RuleResult,
    ShieldConfig,
)

__all__ = [
    "PolicyEngine",
    "PolicyDecision",
    "PolicyDecisionType",
    "EvaluationContext",
    "MerchantPolicy",
    "ShieldConfig",
    "RuleResult",
    "RuleDisposition",
    "PolicyRule",
    "default_rule_set",
    "EvaluationOutcome",
    "evaluate_rules",
    "PolicyError",
    "InvalidPolicyContextError",
    "PolicyEvaluationError",
    "UnknownRuleError",
]
