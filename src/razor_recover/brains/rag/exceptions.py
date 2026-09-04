"""Centralized exceptions for the RAG / knowledge-base layer.

External failures (e.g. Qdrant, embedding providers) are normalized to these
domain exceptions so they never leak raw provider errors through the rest of
the application.
"""

from __future__ import annotations


class RAGError(Exception):
    """Base exception for the RAG / knowledge-base layer."""


class DocumentError(RAGError):
    """Raised for invalid or malformed knowledge documents."""


class EmbeddingError(RAGError):
    """Raised when an embedding provider cannot produce embeddings."""


class VectorStoreError(RAGError):
    """Raised when the vector store cannot be reached or queried."""


class CollectionNotFoundError(VectorStoreError):
    """Raised when an expected vector-store collection is missing."""


class RetrieverError(RAGError):
    """Raised when retrieval fails or returns malformed data."""


__all__ = [
    "RAGError",
    "DocumentError",
    "EmbeddingError",
    "VectorStoreError",
    "CollectionNotFoundError",
    "RetrieverError",
]
