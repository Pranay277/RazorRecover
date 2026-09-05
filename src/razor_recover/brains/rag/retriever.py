"""Reusable RAG retriever.

Retrieval is purely a look-up of relevant knowledge/context; it does NOT make
any recovery decision. The caller (e.g. a future LLM agent) consumes the
structured results, and the Policy Engine remains the final authorization layer.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from razor_recover.brains.rag.embeddings import EmbeddingProvider
from razor_recover.brains.rag.exceptions import RetrieverError, VectorStoreError
from razor_recover.brains.rag.schemas import RetrievalHit, RetrievalResult
from razor_recover.brains.rag.vector_store import VectorStore
from razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.rag.retriever")

DEFAULT_TOP_K = 5


def format_hit(raw: Mapping[str, Any]) -> RetrievalHit:
    """Convert a raw vector-store hit into a structured :class:`RetrievalHit`."""
    payload = raw.get("payload") or {}
    return RetrievalHit(
        id=str(payload.get("id") or raw.get("id", "")),
        document_id=str(payload.get("document_id", "")),
        category=str(payload.get("category", "unknown")),
        merchant_scope=payload.get("merchant_scope"),
        source=str(payload.get("source", "unknown")),
        score=_clamp(float(raw.get("score", 0.0))),
        content=str(raw.get("content") or payload.get("content", "")),
    )


def format_result(
    query: str,
    merchant_id: str | None,
    top_k: int,
    raw_hits: list[Mapping[str, Any]],
) -> RetrievalResult:
    """Format a list of raw hits into a structured retrieval result."""
    return RetrievalResult(
        query=query,
        merchant_id=merchant_id,
        top_k=top_k,
        hits=[format_hit(h) for h in raw_hits],
    )


def _clamp(score: float) -> float:
    return max(0.0, min(1.0, score))


class Retriever:
    """Retrieves merchant/recovery-policy context from a vector store.

    Composed via dependency injection with a :class:`VectorStore` and an
    :class:`EmbeddingProvider` so it is independently testable and the concrete
    providers can be swapped.
    """

    def __init__(
        self,
        store: VectorStore,
        embeddings: EmbeddingProvider,
        collection: str,
        default_top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self.store = store
        self.embeddings = embeddings
        self.collection = collection
        self.default_top_k = max(1, int(default_top_k))

    def _validate_top_k(self, top_k: int | None) -> int:
        if top_k is None:
            return self.default_top_k
        if int(top_k) < 1:
            raise RetrieverError("top_k must be a positive integer.")
        return int(top_k)

    def _merchant_filter(self, merchant_id: str | None) -> dict | None:
        # Exact-match merchant scoping. Omit the filter for global context.
        return {"merchant_scope": merchant_id} if merchant_id else None

    def retrieve(
        self,
        query: str,
        merchant_id: str | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        """Return structured, top-k knowledge chunks relevant to ``query``.

        When ``merchant_id`` is supplied, only knowledge scoped to that merchant
        is returned.
        """
        if not query or not query.strip():
            raise RetrieverError("Query must be a non-empty string.")

        k = self._validate_top_k(top_k)
        try:
            query_vector = self.embeddings.embed(query)
        except Exception as exc:
            if isinstance(exc, RetrieverError):
                raise
            logger.exception("Embedding query failed")
            raise RetrieverError(f"Failed to embed query: {exc}") from exc

        try:
            raw_hits = self.store.search(
                self.collection,
                query_vector,
                k,
                filters=self._merchant_filter(merchant_id),
            )
        except VectorStoreError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Vector-store search failed")
            raise RetrieverError(f"Retrieval failed: {exc}") from exc

        return format_result(
            query=query, merchant_id=merchant_id, top_k=k, raw_hits=raw_hits
        )
