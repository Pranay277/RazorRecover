"""Typed representations for the RAG knowledge base and retrieval layer.

Keeps the schema (document/chunk/result) separate from loading, embedding,
storage and retrieval logic so responsibilities stay clean.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """A knowledge-base article. ``merchant_scope`` may be set to restrict a
    document to a specific merchant; ``None`` means it applies globally."""

    id: str
    category: str
    title: str
    content: str
    merchant_scope: str | None = None
    source: str = "synthetic-demo"
    tags: list[str] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    """A single chunk of a knowledge-base document ready to be embedded."""

    id: str
    document_id: str
    content: str
    chunk_index: int
    category: str
    merchant_scope: str | None = None
    source: str = "synthetic-demo"
    tags: list[str] = Field(default_factory=list)

    @property
    def payload(self) -> dict:
        """Stable dictionary form used as the vector-store payload."""
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "category": self.category,
            "merchant_scope": self.merchant_scope,
            "source": self.source,
            "tags": self.tags,
        }


class RetrievalHit(BaseModel):
    """A single retrieved knowledge chunk with its relevance metadata."""

    id: str
    document_id: str
    category: str
    merchant_scope: str | None
    source: str
    score: float = Field(ge=0.0, le=1.0)
    content: str


class RetrievalResult(BaseModel):
    """Structured result of a retrieval query."""

    query: str
    merchant_id: str | None
    top_k: int
    hits: list[RetrievalHit] = Field(default_factory=list)
