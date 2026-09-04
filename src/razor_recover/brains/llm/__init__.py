"""AI decision agent (LLM) layer - RECOMMENDS, never executes.

Public exports for the reusable decision component. See individual modules for
provider isolation, prompt construction, schemas and orchestration.
"""

from src.razor_recover.brains.llm.agent import DecisionAgent, parse_decision
from src.razor_recover.brains.llm.exceptions import (
    InvalidAgentInputError,
    InvalidDecisionError,
    LLMError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
    LLMProviderUnavailableError,
)
from src.razor_recover.brains.llm.providers import (
    LLMProvider,
    OllamaProvider,
    create_llm_provider,
)
from src.razor_recover.brains.llm.schemas import (
    AgentDecision,
    AllowedAction,
    CustomerSnapshot,
    DecisionRequest,
    MerchantSnapshot,
    TransactionSnapshot,
)
from src.razor_recover.brains.llm.service import DecisionAgentService

__all__ = [
    "DecisionAgent",
    "DecisionAgentService",
    "parse_decision",
    "LLMProvider",
    "OllamaProvider",
    "create_llm_provider",
    "AgentDecision",
    "AllowedAction",
    "DecisionRequest",
    "TransactionSnapshot",
    "CustomerSnapshot",
    "MerchantSnapshot",
    "LLMError",
    "LLMProviderError",
    "LLMProviderUnavailableError",
    "LLMTimeoutError",
    "LLMResponseError",
    "InvalidAgentInputError",
    "InvalidDecisionError",
]
