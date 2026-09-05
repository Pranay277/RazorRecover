"""Integration test for the RAG layer against a live Qdrant instance.

Skipped when Qdrant is unavailable. Uses a uniquely named collection so it does
not interfere with other collections, and always deletes it in teardown.
"""

import pytest

from razor_recover.brains.rag.embeddings import LocalHashEmbeddingProvider
from razor_recover.brains.rag.knowledge_base import load_documents
from razor_recover.brains.rag.schemas import KnowledgeDocument
from razor_recover.brains.rag.seeder import seed_knowledge_base
from razor_recover.brains.rag.service import RAGService
from razor_recover.brains.rag.vector_store import QdrantVectorStore


@pytest.fixture
def qdrant_store():
    store = QdrantVectorStore(url="http://localhost:6333")
    if not store.ping():
        pytest.skip("Qdrant unavailable at localhost:6333")
    yield store
    store._client.close()


@pytest.fixture
def qdrant_service(qdrant_store):
    collection = "test_rag_qdrant"
    svc = RAGService(
        store=qdrant_store,
        embeddings=LocalHashEmbeddingProvider(dimension=128),
        collection=collection,
    )
    if svc.store.collection_exists(collection):
        svc.store.delete_collection(collection)
    yield svc
    svc.store.delete_collection(collection)


def test_seed_and_retrieve_against_qdrant(qdrant_service):
    svc = qdrant_service
    docs = [
        KnowledgeDocument(
            id="global::retry",
            category="retry_limits",
            title="Retry limits",
            content="Global guidance: network timeouts may be retried up to three times.",
        ),
        KnowledgeDocument(
            id="nimbus::policy",
            category="merchant_recovery_policy",
            title="Nimbus policy",
            merchant_scope="Nimbus Retail",
            content="Nimbus Retail: escalate high value failed payments to manual review.",
        ),
        KnowledgeDocument(
            id="vertex::policy",
            category="merchant_recovery_policy",
            title="Vertex policy",
            merchant_scope="Vertex Electronics",
            content="Vertex Electronics: prefer fresh payment links over blind retries.",
        ),
    ]
    indexed = seed_knowledge_base(svc.store, svc.embeddings, svc.collection, documents=docs)
    assert indexed == 3
    assert svc.store.count(svc.collection) == 3

    # Global retrieval
    global_result = svc.retrieve("retry network timeout", top_k=5)
    assert global_result.hits

    # Merchant-scoped retrieval
    scoped = svc.retrieve("payment manual review", merchant_id="Nimbus Retail", top_k=5)
    assert scoped.hits
    for h in scoped.hits:
        assert h.merchant_scope == "Nimbus Retail"
        assert 0.0 <= h.score <= 1.0


def test_seed_full_demo_knowledge_base_against_qdrant(qdrant_service):
    svc = qdrant_service
    from razor_recover.brains.rag.knowledge_base import DEMO_KNOWLEDGE_DOCUMENTS

    seed_knowledge_base(svc.store, svc.embeddings, svc.collection, documents=DEMO_KNOWLEDGE_DOCUMENTS)
    assert svc.store.count(svc.collection) >= len(DEMO_KNOWLEDGE_DOCUMENTS)

    # Merchant-specific context is returned for a scoped merchant.
    result = svc.retrieve("payment policy", merchant_id="Nimbus Retail", top_k=5)
    assert result.hits
    assert all(h.merchant_scope == "Nimbus Retail" for h in result.hits)
