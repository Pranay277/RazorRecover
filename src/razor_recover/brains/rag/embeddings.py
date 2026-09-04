"""Embedding generation, isolated behind a provider interface.

Retrieval depends only on the :class:`EmbeddingProvider` protocol, so the rest
of the RAG layer is independent of any particular provider/model. A concrete
provider is selected via the application settings (``RAG_EMBEDDING_PROVIDER``).

Two providers ship with the MVP:

* :class:`LocalHashEmbeddingProvider` - deterministic, network-free, hash-based
  bag-of-token vectors. Great for demo/tests because it requires no model
  server and yields reproducible results.
* :class:`OllamaEmbeddingProvider` - a configurable HTTP embedding backend
  (currently a thin, tested-callable implementation).
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Protocol

import numpy as np

from src.razor_recover.brains.rag.exceptions import EmbeddingError
from src.razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.rag.embeddings")


class EmbeddingProvider(Protocol):
    """Interface every embedding provider must satisfy."""

    dimension: int

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class _BaseEmbeddingProvider(ABC):
    """Shared validation/error handling for concrete providers."""

    dimension: int

    def _validate(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingError("Cannot embed an empty/invalid text.")
        return text.strip()

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        try:
            return [self.embed(t) for t in texts]
        except EmbeddingError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Embedding batch failed")
            raise EmbeddingError(f"Embedding batch failed: {exc}") from exc


class LocalHashEmbeddingProvider(_BaseEmbeddingProvider):
    """Deterministic, network-free bag-of-token hashed embeddings.

    Each normalized token hashes into a fixed-dimension vector; token vectors
    are summed and L2-normalized. Cosine similarity therefore approximates
    lexical overlap, which is adequate for the synthetic/demo knowledge base
    and makes every integration reproducible without a model server.
    """

    def __init__(self, dimension: int = 256) -> None:
        if dimension <= 0:
            raise EmbeddingError("Embedding dimension must be positive.")
        self.dimension = int(dimension)

    def _token_hashes(self, text: str) -> list[int]:
        tokens = text.lower().split()
        return [
            int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16)
            for t in tokens
        ]

    def embed(self, text: str) -> list[float]:
        text = self._validate(text)
        vec = np.zeros(self.dimension, dtype=np.float64)
        for token_hash in self._token_hashes(text):
            idx = token_hash % self.dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [round(float(v), 6) for v in vec]


class OllamaEmbeddingProvider(_BaseEmbeddingProvider):
    """HTTP embedding provider (e.g. Ollama ``/api/embed``).

    Configuration is resolved via the application settings. The HTTP call is
    kept behind this small adapter so the rest of RAG is unaffected if the
    provider changes.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        dimension: int,
        timeout: float = 30.0,
    ) -> None:
        import httpx  # lazy: only needed when this provider is used

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimension = int(dimension)
        self._timeout = timeout
        self._client = httpx.Client(timeout=self._timeout, base_url=self.base_url)

    def embed(self, text: str) -> list[float]:
        text = self._validate(text)
        try:
            resp = self._client.post(
                "/api/embed",
                json={"model": self.model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings")
            vector = embeddings[0] if isinstance(embeddings, list) else None
            if vector is None:
                raise ValueError("No embedding returned by provider.")
            return [float(x) for x in vector][: self.dimension]
        except Exception as exc:
            logger.exception("Ollama embedding request failed")
            raise EmbeddingError(f"Embedding provider request failed: {exc}") from exc


def create_embedding_provider(
    provider: str,
    dimension: int,
    model: str | None = None,
    base_url: str | None = None,
) -> EmbeddingProvider:
    """Factory: build an embedding provider from configuration."""
    name = (provider or "hash").lower().strip()
    if name in ("hash", "local", "localhash"):
        return LocalHashEmbeddingProvider(dimension=dimension)
    if name in ("ollama", "ollamaembed"):
        return OllamaEmbeddingProvider(
            base_url=base_url or "http://localhost:11434",
            model=model or "nomic-embed-text",
            dimension=dimension,
        )
    raise EmbeddingError(f"Unknown embedding provider: {provider!r}")
