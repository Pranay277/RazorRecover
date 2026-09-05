"""Recovery workflow - the first complete backend vertical slice.

Coordinates ML -> RAG -> LLM -> Policy -> Execution -> persistence -> audit for
a single failed payment. The API layer is intentionally thin; all decision work
happens here behind the :class:`RecoveryOrchestrator`.
"""

from razor_recover.workflow.exceptions import (
    LLMStageError,
    MLStageError,
    MerchantNotFoundError,
    PolicyStageError,
    TransactionNotFoundError,
    WorkflowError,
    WorkflowStageError,
)
from razor_recover.workflow.orchestrator import RecoveryOrchestrator
from razor_recover.workflow.ports import (
    AgentServicePort,
    MerchantPolicyProviderPort,
    PredictionServicePort,
    RagServicePort,
)
from razor_recover.workflow.policy import (
    DefaultMerchantPolicyProvider,
    MerchantPolicyProvider,
)
from razor_recover.workflow.schemas import EvaluateRequest, EvaluateResponse

__all__ = [
    "RecoveryOrchestrator",
    "EvaluateRequest",
    "EvaluateResponse",
    "AgentServicePort",
    "RagServicePort",
    "PredictionServicePort",
    "MerchantPolicyProviderPort",
    "MerchantPolicyProvider",
    "DefaultMerchantPolicyProvider",
    "WorkflowError",
    "WorkflowStageError",
    "TransactionNotFoundError",
    "MerchantNotFoundError",
    "MLStageError",
    "LLMStageError",
    "PolicyStageError",
]
