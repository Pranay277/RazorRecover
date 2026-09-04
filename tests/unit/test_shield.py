"""Unit tests for the Policy / Safety Engine (shield).

Pure deterministic tests with constructed inputs - never require Ollama or any
network/LLM dependency. The engine must authorize without ever consulting the
LLM.
"""

import copy

import pytest

from src.razor_recover.brains.llm.schemas import (
    AgentDecision,
    AllowedAction,
    TransactionSnapshot,
)
from src.razor_recover.shield.policy_engine import PolicyEngine
from src.razor_recover.shield.rules import PolicyRule
from src.razor_recover.shield.schemas import (
    EvaluationContext,
    MerchantPolicy,
    PolicyDecision,
    PolicyDecisionType,
    RuleDisposition,
    RuleResult,
    ShieldConfig,
)
from src.razor_recover.shield.exceptions import (
    InvalidPolicyContextError,
    PolicyEvaluationError,
    UnknownRuleError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_transaction(amount: float = 100.0) -> TransactionSnapshot:
    return TransactionSnapshot(
        external_id="tx_1",
        amount=amount,
        currency="USD",
        failure_code="card_declined",
        failure_reason="declined",
        payment_method="card",
        gateway="stripe",
        attempt_number=1,
    )


def make_policy(
    retry_enabled: bool = True,
    max_retries: int | None = 3,
    max_risk_score: float | None = 0.70,
    min_recovery_probability: float | None = 0.30,
    high_value_threshold: float | None = 10_000.0,
    customer_notifications_enabled: bool = True,
    disallowed_actions: list[AllowedAction] | None = None,
    policy_version: int = 2,
) -> MerchantPolicy:
    return MerchantPolicy(
        merchant_external_id="mch_1",
        retry_enabled=retry_enabled,
        max_retries=max_retries,
        max_risk_score=max_risk_score,
        min_recovery_probability=min_recovery_probability,
        high_value_threshold=high_value_threshold,
        customer_notifications_enabled=customer_notifications_enabled,
        disallowed_actions=disallowed_actions or [],
        policy_version=policy_version,
    )


def make_decision(action: AllowedAction) -> AgentDecision:
    return AgentDecision(
        transaction_external_id="tx_1",
        action=action,
        rationale="recommended by agent",
        confidence=0.8,
    )


def make_context(
    action: AllowedAction | None,
    *,
    agent_decision: AgentDecision | None = None,
    transaction: TransactionSnapshot | object | None = None,
    merchant_policy: MerchantPolicy | None = None,
    risk_score: float | None = 0.4,
    recovery_probability: float | None = 0.6,
    retry_attempts: int | None = 0,
    history_available: bool = True,
) -> EvaluationContext:
    if transaction is None:
        transaction = make_transaction()
    return EvaluationContext(
        requested_action=action,
        agent_decision=agent_decision,
        transaction=transaction,  # type: ignore[arg-type]
        merchant_policy=merchant_policy,
        risk_score=risk_score,
        recovery_probability=recovery_probability,
        retry_attempts=retry_attempts,
        history_available=history_available,
    )


# ---------------------------------------------------------------------------
# 1. Valid RETRY_NOW -> ALLOW
# ---------------------------------------------------------------------------

def test_valid_retry_now_allowed():
    engine = PolicyEngine()
    ctx = make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy())
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.final_action == "RETRY_NOW"
    assert decision.requested_action == "RETRY_NOW"


# ---------------------------------------------------------------------------
# 2. High risk -> BLOCK
# ---------------------------------------------------------------------------

def test_high_risk_blocks_retry():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(max_risk_score=0.70),
        risk_score=0.85,
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert decision.final_action is None
    assert any("risk" in r.lower() for r in decision.reasons)


# ---------------------------------------------------------------------------
# 3. Low recovery probability -> REVIEW
# ---------------------------------------------------------------------------

def test_low_recovery_probability_reviews():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(min_recovery_probability=0.30),
        recovery_probability=0.10,
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.REVIEW
    assert decision.final_action is None
    assert any("recovery" in r.lower() for r in decision.reasons)


# ---------------------------------------------------------------------------
# 4. Retry limit exceeded -> BLOCK
# ---------------------------------------------------------------------------

def test_retry_limit_exceeded_blocks():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(max_retries=3),
        retry_attempts=3,
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert any("limit" in r.lower() for r in decision.reasons)


# ---------------------------------------------------------------------------
# 5. Merchant retry disabled -> BLOCK
# ---------------------------------------------------------------------------

def test_merchant_retry_disabled_blocks():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(retry_enabled=False),
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert any("disabled" in r.lower() for r in decision.reasons)


# ---------------------------------------------------------------------------
# 6. High-value transaction -> REVIEW
# ---------------------------------------------------------------------------

def test_high_value_transaction_reviews():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(high_value_threshold=10000.0),
        transaction=make_transaction(amount=20_000.0),
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.REVIEW
    assert any("high-value" in r.lower() for r in decision.reasons)


def test_high_value_flag_does_not_apply_to_stop():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.STOP, merchant_policy=make_policy(),
        transaction=make_transaction(amount=50_000.0),
    )
    assert engine.evaluate(ctx).decision == PolicyDecisionType.BLOCK


# ---------------------------------------------------------------------------
# 7. MANUAL_REVIEW -> REVIEW
# ---------------------------------------------------------------------------

def test_manual_review_always_reviews():
    engine = PolicyEngine()
    ctx = make_context(AllowedAction.MANUAL_REVIEW, merchant_policy=make_policy())
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.REVIEW
    assert decision.final_action is None


# ---------------------------------------------------------------------------
# 8. STOP -> BLOCK
# ---------------------------------------------------------------------------

def test_stop_always_blocks():
    engine = PolicyEngine()
    ctx = make_context(AllowedAction.STOP, merchant_policy=make_policy())
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert decision.final_action is None


# ---------------------------------------------------------------------------
# 9. Unknown action -> BLOCK
# ---------------------------------------------------------------------------

def test_unknown_action_blocks():
    engine = PolicyEngine()
    ctx = make_context(None, merchant_policy=make_policy())
    ctx.requested_action = "EXECUTE_RETRY_NOW"  # type: ignore[assignment]
    # ManualReviewActionRule compares against None - ensure allowlist catches it.
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert any("not an allowed action" in r for r in decision.reasons)


def test_missing_action_blocks():
    engine = PolicyEngine()
    ctx = make_context(None, merchant_policy=make_policy())
    # Set a non-enum string so allowlist treats it as unknown/missing.
    ctx.requested_action = None
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK


# ---------------------------------------------------------------------------
# 10. Missing risk score -> fail closed
# ---------------------------------------------------------------------------

def test_missing_risk_score_fails_closed():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(),
        risk_score=None,
    )
    decision = engine.evaluate(ctx)
    assert decision.decision != PolicyDecisionType.ALLOW
    assert decision.decision in (PolicyDecisionType.REVIEW, PolicyDecisionType.BLOCK)
    assert any("risk" in r.lower() for r in decision.reasons)


# ---------------------------------------------------------------------------
# 11. Missing policy -> fail closed
# ---------------------------------------------------------------------------

def test_missing_policy_fails_closed_for_retry():
    engine = PolicyEngine()
    ctx = make_context(AllowedAction.RETRY_NOW, merchant_policy=None)
    decision = engine.evaluate(ctx)
    assert decision.decision != PolicyDecisionType.ALLOW
    assert any("policy" in r.lower() for r in decision.reasons)


def test_missing_policy_fails_closed_for_notification():
    engine = PolicyEngine()
    ctx = make_context(AllowedAction.CUSTOMER_NOTIFICATION, merchant_policy=None)
    decision = engine.evaluate(ctx)
    assert decision.decision != PolicyDecisionType.ALLOW
    assert any("policy" in r.lower() for r in decision.reasons)


# ---------------------------------------------------------------------------
# 12. Multiple rule failures -> all reasons captured
# ---------------------------------------------------------------------------

def test_multiple_failures_capture_all_reasons():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(max_retries=2, max_risk_score=0.70,
                                    min_recovery_probability=0.30),
        risk_score=0.9,
        recovery_probability=0.1,
        retry_attempts=2,
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    joined = " ".join(r.lower() for r in decision.reasons)
    assert "risk" in joined
    assert "limit" in joined
    assert "recovery" in joined


# ---------------------------------------------------------------------------
# 13. Valid DELAYED_RETRY -> ALLOW
# ---------------------------------------------------------------------------

def test_valid_delayed_retry_allowed():
    engine = PolicyEngine()
    ctx = make_context(AllowedAction.DELAYED_RETRY, merchant_policy=make_policy())
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.final_action == "DELAYED_RETRY"


def test_valid_alternative_payment_allowed():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.ALTERNATIVE_PAYMENT, merchant_policy=make_policy(), risk_score=0.3
    )
    assert engine.evaluate(ctx).decision == PolicyDecisionType.ALLOW


def test_alternative_payment_high_risk_reviews():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.ALTERNATIVE_PAYMENT,
        merchant_policy=make_policy(max_risk_score=0.70),
        risk_score=0.9,
    )
    assert engine.evaluate(ctx).decision == PolicyDecisionType.REVIEW


# ---------------------------------------------------------------------------
# 14. Valid customer notification -> ALLOW
# ---------------------------------------------------------------------------

def test_valid_customer_notification_allowed():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.CUSTOMER_NOTIFICATION, merchant_policy=make_policy()
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.final_action == "CUSTOMER_NOTIFICATION"


def test_notifications_disabled_blocks():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.CUSTOMER_NOTIFICATION,
        merchant_policy=make_policy(customer_notifications_enabled=False),
    )
    assertion = engine.evaluate(ctx)
    assert assertion.decision == PolicyDecisionType.BLOCK


# ---------------------------------------------------------------------------
# 15. Policy evaluation exception -> BLOCK (fail closed)
# ---------------------------------------------------------------------------

class _ExplodingRule(PolicyRule):
    name = "exploding_rule"

    def evaluate(self, context):  # noqa: D102
        raise RuntimeError("boom")


def test_rule_exception_fails_closed():
    engine = PolicyEngine(rules=[_ExplodingRule()])
    ctx = make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy())
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert any("fail" in r.lower() for r in decision.reasons)


def test_engine_evaluate_with_bad_type_raises():
    engine = PolicyEngine()
    with pytest.raises(InvalidPolicyContextError):
        engine.evaluate({"not": "a context"})  # type: ignore[arg-type]


def test_run_unknown_rule_raises():
    engine = PolicyEngine()
    with pytest.raises(UnknownRuleError):
        engine.run_rule(make_context(AllowedAction.STOP), "does_not_exist")


# ---------------------------------------------------------------------------
# 16. Determinism
# ---------------------------------------------------------------------------

def test_policy_decision_is_deterministic():
    ctx = make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy())
    d1 = PolicyEngine().evaluate(copy.deepcopy(ctx))
    d2 = PolicyEngine().evaluate(copy.deepcopy(ctx))
    assert d1.decision == d2.decision
    assert [r.rule_name for r in d1.rule_results] == [r.rule_name for r in d2.rule_results]
    assert [r.passed for r in d1.rule_results] == [r.passed for r in d2.rule_results]


def test_identical_input_produces_identical_decision():
    ctx1 = make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy())
    ctx2 = make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy())
    e1 = PolicyEngine().evaluate(ctx1)
    e2 = PolicyEngine().evaluate(ctx2)
    assert e1.model_dump(exclude={"evaluated_at"}) == e2.model_dump(exclude={"evaluated_at"})


# ---------------------------------------------------------------------------
# Additional: DECISION AUDIT / NO-EXECUTION / FINAL_ACTION semantics
# ---------------------------------------------------------------------------

def test_decision_records_rule_results_and_version():
    engine = PolicyEngine()
    decision = engine.evaluate(
        make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy(policy_version=7))
    )
    assert decision.policy_version == 7
    assert len(decision.rule_results) == len(engine.rule_names)
    assert all(r.rule_name in engine.rule_names for r in decision.rule_results)
    assert decision.requested_action == "RETRY_NOW"


def test_final_action_none_when_not_allowed():
    engine = PolicyEngine()
    blocked = engine.evaluate(
        make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy(),
                     retry_attempts=5)
    )
    assert blocked.decision == PolicyDecisionType.BLOCK
    assert blocked.final_action is None


def test_engine_never_requires_agent_decision():
    # The engine works with explicit requested_action and no LLM decision object,
    # proving it authorizes without consulting the LLM.
    ctx = make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy(),
                       agent_decision=None)
    assert PolicyEngine().evaluate(ctx).decision == PolicyDecisionType.ALLOW


def test_engine_returns_decision_only_no_execution():
    # Nothing here mutates state or calls out; the only observable result is the
    # PolicyDecision (a pure value object).
    decision = PolicyEngine().evaluate(
        make_context(AllowedAction.RETRY_NOW, merchant_policy=make_policy())
    )
    assert isinstance(decision, PolicyDecision)


def test_retry_history_unavailable_prevents_auto_retry():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(),
        retry_attempts=None,
        history_available=False,
    )
    decision = engine.evaluate(ctx)
    assert decision.decision != PolicyDecisionType.ALLOW
    assert any("history" in r.lower() for r in decision.reasons)


def test_merchant_disallowed_action_blocks():
    engine = PolicyEngine()
    ctx = make_context(
        AllowedAction.CUSTOMER_NOTIFICATION,
        merchant_policy=make_policy(
            disallowed_actions=[AllowedAction.CUSTOMER_NOTIFICATION]
        ),
    )
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert any("disallow" in r.lower() for r in decision.reasons)


def test_missing_transaction_blocks():
    engine = PolicyEngine()
    ctx = EvaluationContext(
        requested_action=AllowedAction.RETRY_NOW,
        merchant_policy=make_policy(),
        risk_score=0.4,
        recovery_probability=0.6,
        retry_attempts=0,
    )  # transaction omitted -> None
    decision = engine.evaluate(ctx)
    assert decision.decision == PolicyDecisionType.BLOCK
    assert any("transaction" in r.lower() for r in decision.reasons)


def test_config_from_settings_defaults():
    cfg = ShieldConfig.from_settings(None)
    assert cfg.default_max_retries == 3
    assert cfg.default_max_risk_score == 0.70
    assert cfg.policy_version == 1
