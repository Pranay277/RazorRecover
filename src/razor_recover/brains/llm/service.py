"""Decision-agent service: wires configuration -> provider -> agent.

This is the reusable composition root for the AI decision component. It reads
the configured LLM provider from settings and exposes a single ``recommend``
facade. It keeps provider selection in one place so the agent stays provider-
agnostic.
"""

from __future__ import annotations

import logging

from src.razor_recover.brains.llm.agent import DecisionAgent
from src.razor_recover.brains.llm.providers import LLMProvider, create_llm_provider
from src.razor_recover.brains.llm.schemas import AgentDecision, DecisionRequest
from src.razor_recover.config import Settings, get_settings
from src.razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.llm.service")


class DecisionAgentService:
    """High-level facade for generating recovery recommendations."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        self.agent = DecisionAgent(provider)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "DecisionAgentService":
        settings = settings or get_settings()
        provider = create_llm_provider(
            provider=settings.llm_provider,
            base_url=settings.ollama_url,
            model=settings.ollama_model,
            temperature=settings.llm_temperature,
            num_predict=settings.llm_num_predict,
            timeout=settings.llm_timeout_seconds,
        )
        return cls(provider=provider)

    def recommend(self, request: DecisionRequest) -> AgentDecision:
        """Generate and validate a recovery recommendation for a request."""
        return self.agent.decide(request)

    def is_available(self) -> bool:
        return self.provider.is_available()
