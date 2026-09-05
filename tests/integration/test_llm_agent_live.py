"""Optional live-Ollama integration test for the AI decision agent.

Skips automatically when Ollama is not reachable or not configured, so the
default test run never depends on an external model. Intended to be run
manually / in an environment with Ollama running.
"""

import pytest

from razor_recover.brains.llm.agent import DecisionAgent
from razor_recover.brains.llm.schemas import (
    AllowedAction,
    CustomerSnapshot,
    DecisionRequest,
    MerchantSnapshot,
    TransactionSnapshot,
)
from razor_recover.brains.llm.service import DecisionAgentService


def _live_provider_or_skip():
    service = DecisionAgentService.from_settings()
    if not service.is_available():
        pytest.skip("Ollama is not reachable - skipping live integration test")
    return service.provider


def _request() -> DecisionRequest:
    return DecisionRequest(
        transaction=TransactionSnapshot(
            external_id="tx_live_1",
            amount=99.99,
            currency="USD",
            failure_code="bank_decline",
            failure_reason="bank declined the transaction",
            payment_method="card",
            gateway="stripe",
            attempt_number=1,
        ),
        customer=CustomerSnapshot(
            external_id="cst_live", prior_successful_count=12, prior_failed_count=0
        ),
        merchant=MerchantSnapshot(external_id="mch_live", name="Nimbus", industry="retail"),
        risk_score=0.2,
        recovery_probability=0.7,
        request_id="req_live",
    )


def test_live_ollama_returns_valid_decision():
    provider = _live_provider_or_skip()
    agent = DecisionAgent(provider)
    decision = agent.decide(_request())
    assert decision.transaction_external_id == "tx_live_1"
    assert decision.action in AllowedAction
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.rationale
