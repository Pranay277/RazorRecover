"""Injection contracts (ports) the workflow orchestrator depends on.

Defining these as protocols keeps the orchestrator decoupled from concrete ML,
RAG, LLM and policy implementations, so each can be swapped (or faked in tests)
without touching the coordinator.
"""

from __future__ import annotations

from typing import Protocol

from razor_recover.brains.llm.schemas import (
    AgentDecision,
    DecisionRequest,
)


class PredictionServicePort(Protocol):
    """ML scoring port: turns a transaction into risk/recovery predictions."""

    def predict_single(self, transaction) -> object:
        """Return an object with ``risk_score`` and ``recovery_probability``."""
        ...


class RagServicePort(Protocol):
    """RAG retrieval port."""

    def retrieve(self, query: str, merchant_id: str | None, top_k: int) -> object:
        """Return a retrieval result (or None on best-effort failure)."""
        ...


class AgentServicePort(Protocol):
    """LLM decision-agent port."""

    def recommend(self, request: DecisionRequest) -> AgentDecision: ...


class MerchantPolicyProviderPort(Protocol):
    """Resolves the merchant policy for an evaluation."""

    def get_policy(self, merchant_external_id: str | None): ...


__all__ = [
    "PredictionServicePort",
    "RagServicePort",
    "AgentServicePort",
    "MerchantPolicyProviderPort",
]
