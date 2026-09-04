"""LLM provider abstraction.

Decision logic depends only on the :class:`LLMProvider` protocol. Ollama-specific
details are isolated in :class:`OllamaProvider` so the provider can be swapped
later without touching the agent. Provider failures are normalized to the
project's ``brains.llm.exceptions`` exceptions.
"""

from __future__ import annotations

import logging
from typing import Protocol, Sequence

import httpx

from src.razor_recover.brains.llm.exceptions import (
    LLMProviderError,
    LLMProviderUnavailableError,
    LLMTimeoutError,
)
from src.razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.llm.providers")

Message = dict[str, str]  # {"role": ..., "content": ...}


class LLMProvider(Protocol):
    """Every LLM provider must satisfy this interface."""

    name: str
    model: str

    def complete(self, messages: Sequence[Message]) -> str: ...

    def is_available(self) -> bool: ...


class OllamaProvider:
    """Ollama-backed chat completion provider (local Llama 3)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3:latest",
        temperature: float = 0.2,
        num_predict: int = 800,
        timeout: float = 60.0,
    ) -> None:
        self.name = "ollama"
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._num_predict = num_predict
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def is_available(self) -> bool:
        try:
            resp = self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def complete(self, messages: Sequence[Message]) -> str:
        payload = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self._temperature,
                "num_predict": self._num_predict,
            },
        }
        try:
            resp = self._client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning("Ollama call timed out after %ss", self._timeout)
            raise LLMTimeoutError(
                f"Ollama call timed out after {self._timeout}s."
            ) from exc
        except httpx.ConnectError as exc:
            logger.warning("Ollama not reachable at %s", self._base_url)
            raise LLMProviderUnavailableError(
                f"Ollama is not reachable at {self._base_url}."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama returned HTTP %s", exc.response.status_code)
            raise LLMProviderError(
                f"Ollama returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        try:
            data = resp.json()
            return data["message"]["content"]
        except (KeyError, ValueError) as exc:
            logger.error("Ollama returned unexpected payload")
            raise LLMProviderError("Ollama returned an unexpected response shape.") from exc


def create_llm_provider(
    provider: str = "ollama",
    base_url: str = "http://localhost:11434",
    model: str = "llama3:latest",
    temperature: float = 0.2,
    num_predict: int = 800,
    timeout: float = 60.0,
) -> LLMProvider:
    """Factory: build an LLM provider from configuration."""
    name = (provider or "ollama").lower().strip()
    if name == "ollama":
        return OllamaProvider(
            base_url=base_url,
            model=model,
            temperature=temperature,
            num_predict=num_predict,
            timeout=timeout,
        )
    raise LLMProviderError(f"Unknown LLM provider: {provider!r}")
