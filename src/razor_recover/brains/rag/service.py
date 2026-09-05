"""RAG service: composition root + high-level facade for the RAG layer.

Builds the concrete embedding provider and vector store from application
settings and exposes retrieval and seeding through one interface. This keeps
provider/store selection in one place (dependency injection) so individual RAG
components stay replaceable and independently testable.
"""

from __future__ import annotations

import logging

from razor_recover.brains.rag.embeddings import (
    EmbeddingProvider,
    create_embedding_provider,
)
from razor_recover.brains.rag.retriever import Retriever
from razor_recover.brains.rag.schemas import KnowledgeDocument, RetrievalResult
from razor_recover.brains.rag.seeder import seed_knowledge_base
from razor_recover.brains.rag.vector_store import (
    VectorStore,
    create_vector_store,
)
from razor_recover.config import Settings, get_settings
from razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.rag.service")


class RAGService:
    """High-level RAG facade wired from configuration (or injected stores)."""

    def __init__(
        self,
        store: VectorStore | None = None,
        embeddings: EmbeddingProvider | None = None,
        collection: str | None = None,
        default_top_k: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.collection = collection or self.settings.qdrant_collection

        self.store: VectorStore = store or create_vector_store(
            self.settings.qdrant_url, storage="qdrant"
        )
        self.embeddings: EmbeddingProvider = embeddings or create_embedding_provider(
            provider=self.settings.rag_embedding_provider,
            dimension=self.settings.rag_embedding_dim,
            model=self.settings.rag_embedding_model,
            base_url=self.settings.ollama_url,
        )
        self.retriever = Retriever(
            store=self.store,
            embeddings=self.embeddings,
            collection=self.collection,
            default_top_k=default_top_k or self.settings.rag_default_top_k,
        )

    # -- retrieval ----------------------------------------------------------
    def retrieve(
        self,
        query: str,
        merchant_id: str | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        return self.retriever.retrieve(query, merchant_id=merchant_id, top_k=top_k)

    # -- seeding ------------------------------------------------------------
    def seed(
        self,
        documents: list[KnowledgeDocument] | None = None,
    ) -> int:
        """Seed (or reseed) the knowledge base; returns chunks indexed."""
        return seed_knowledge_base(
            self.store,
            self.embeddings,
            self.collection,
            documents=documents,
        )

    def ping(self) -> bool:
        return self.store.ping()
