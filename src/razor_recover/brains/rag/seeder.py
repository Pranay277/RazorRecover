"""Seeding the knowledge base into the vector store.

Ties document loading -> chunking -> embedding -> upsert together. Re-running
the seed recreates the target collection from scratch, so it is idempotent and
safely rerunnable.
"""

from __future__ import annotations

import logging

from razor_recover.brains.rag.chunking import DEFAULT_MAX_CHARS, chunk_document
from razor_recover.brains.rag.embeddings import EmbeddingProvider
from razor_recover.brains.rag.exceptions import DocumentError, VectorStoreError
from razor_recover.brains.rag.knowledge_base import load_documents
from razor_recover.brains.rag.schemas import KnowledgeDocument
from razor_recover.brains.rag.vector_store import VectorPoint, VectorStore
from razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.rag.seeder")


def seed_knowledge_base(
    store: VectorStore,
    embeddings: EmbeddingProvider,
    collection: str,
    documents: list[KnowledgeDocument] | None = None,
    chunk_max_chars: int = DEFAULT_MAX_CHARS,
) -> int:
    """Chunk, embed and index the knowledge base; returns chunks indexed.

    Recreates ``collection`` so reruns are idempotent (no duplicate points).
    """
    if documents is None:
        documents = load_documents()

    chunks = []
    for doc in documents:
        try:
            chunks.extend(chunk_document(doc, max_chars=chunk_max_chars))
        except DocumentError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Chunking failed for %s", doc.id)
            raise DocumentError(f"Failed to chunk document {doc.id}: {exc}") from exc

    if not chunks:
        raise DocumentError("No chunks produced; cannot seed an empty knowledge base.")

    vectors = embeddings.embed_many([c.content for c in chunks])

    points = [
        VectorPoint(
            id=chunk.id,
            vector=vectors[i],
            # payload carries chunk metadata (incl. the original chunk id) plus
            # the chunk content for retrieval. The application chunk id is kept
            # in the payload because Qdrant point ids are UUID-converted.
            payload={**chunk.payload, "id": chunk.id, "content": chunk.content},
        )
        for i, chunk in enumerate(chunks)
    ]

    store.create_collection(collection, embeddings.dimension)
    try:
        indexed = store.upsert(collection, points)
    except VectorStoreError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Upsert failed for collection %s", collection)
        raise VectorStoreError(f"Failed to index knowledge base: {exc}") from exc

    logger.info(
        "Seeded %d documents -> %d chunks into collection %r",
        len(documents),
        indexed,
        collection,
    )
    return indexed
