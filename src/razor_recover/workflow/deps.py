"""Dependency composition root for the recovery workflow.

Builds the full orchestrator from configuration so the API never instantiates
LLM providers, Qdrant clients, ML models, gateways or DB engines inline. Each
component is constructed lazily (nothing connects on startup).
"""

from __future__ import annotations

from razor_recover.brains.ml.service import PredictionService
from razor_recover.brains.rag.service import RAGService
from razor_recover.brains.llm.service import DecisionAgentService
from razor_recover.config import Settings, get_settings
from razor_recover.execution.notification_service import NotificationService
from razor_recover.execution.recovery_service import RecoveryService
from razor_recover.execution.retry_service import RetryService
from razor_recover.shield.policy_engine import PolicyEngine
from razor_recover.shield.schemas import ShieldConfig
from razor_recover.workflow.orchestrator import RecoveryOrchestrator
from razor_recover.workflow.policy import DefaultMerchantPolicyProvider


def build_orchestrator(settings: Settings | None = None) -> RecoveryOrchestrator:
    """Wire every layer into a ready-to-use orchestrator (all lazy)."""
    settings = settings or get_settings()
    config = ShieldConfig.from_settings(settings)

    prediction_service = PredictionService()
    agent_service = DecisionAgentService.from_settings(settings)
    policy_engine = PolicyEngine.from_settings(settings)
    retry_service = RetryService()
    recovery_service = RecoveryService(
        retry_service=retry_service,
        notification_service=NotificationService(),
    )
    merchant_policy_provider = DefaultMerchantPolicyProvider(config=config)
    rag_service = RAGService(settings=settings)

    return RecoveryOrchestrator(
        prediction_service=prediction_service,
        agent_service=agent_service,
        policy_engine=policy_engine,
        recovery_service=recovery_service,
        merchant_policy_provider=merchant_policy_provider,
        rag_service=rag_service,
    )


__all__ = ["build_orchestrator"]
