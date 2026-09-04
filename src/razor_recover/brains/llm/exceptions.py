"""Centralized exceptions for the LLM / decision-agent layer.

Provider failures (e.g. Ollama timeouts / unavailability) are normalized to
these domain exceptions so raw provider errors never leak through the rest of
the application.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for the LLM / decision-agent layer."""


class LLMProviderError(LLMError):
    """The LLM provider could not be reached, timed out, or returned a failure."""


class LLMProviderUnavailableError(LLMProviderError):
    """The LLM provider is not reachable (e.g. Ollama is down)."""


class LLMTimeoutError(LLMProviderError):
    """The LLM provider call exceeded the configured timeout."""


class LLMResponseError(LLMError):
    """The provider returned content that could not be parsed/validated."""


class InvalidAgentInputError(LLMError):
    """The inputs provided to the agent are invalid or incomplete."""


class InvalidDecisionError(LLMResponseError):
    """The provider output failed schema/rules validation."""


__all__ = [
    "LLMError",
    "LLMProviderError",
    "LLMProviderUnavailableError",
    "LLMTimeoutError",
    "LLMResponseError",
    "InvalidAgentInputError",
    "InvalidDecisionError",
]
