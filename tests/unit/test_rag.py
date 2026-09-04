"""Unit tests for the RAG layer (no network required).

Uses the in-memory vector store + deterministic local embeddings so the tests
are fast, network-free and reproducible.
"""

import numpy as np
import pytest

from src.razor_recover.brains.rag.chunking import chunk_document
from src.razor_recover.brains.rag.embeddings import (
    LocalHashEmbeddingProvider,
    create_embedding_provider,
)
from src.razor_recover.brains.rag.exceptions import (
    CollectionNotFoundError,
    DocumentError,
    EmbeddingError,
    RetrieverError,
)
from src.razor_recover.brains.rag.knowledge_base import (
    DEMO_KNOWLEDGE_DOCUMENTS,
    load_documents,
)
from src.razor_recover.brains.rag.retriever import Retriever, format_result
from src.razor_recover.brains.rag.schemas import KnowledgeDocument, RetrievalResult
from src.razor_recover.brains.rag.seeder import seed_knowledge_base
from src.razor_recover.brains.rag.service import RAGService
from src.razor_recover.brains.rag.vector_store import (
    InMemoryVectorStore,
    VectorPoint,
)


def _doc(**kw) -> KnowledgeDocument:
    base = dict(
        id="doc::1",
        category="retry_limits",
        title="Limits",
        content=(
            "Network timeouts may be retried up to three times. "
            "Insufficient funds may be retried up to two times."
        ),
    )
    base.update(kw)
    return KnowledgeDocument(**base)


def _service() -> RAGService:
    store = InMemoryVectorStore()
    embeddings = LocalHashEmbeddingProvider(dimension=128)
    return RAGService(store=store, embeddings=embeddings, collection="test_kb")


# ---------------------------------------------------------------------------
# Document / chunk handling
# ---------------------------------------------------------------------------

def test_load_documents_returns_valid_documents():
    docs = load_documents()
    assert docs
    for d in docs:
        assert d.id and d.category and d.content
    # Ensure the synthetic/demo disclaimer is present (not real policies).
    assert all("SYNTHETIC DEMO" in d.content or "synthetic" in d.source.lower() for d in docs)
    ids = [d.id for d in docs]
    assert len(ids) == len(set(ids))


def test_knowledge_base_has_multiple_categories():
    categories = {d.category for d in DEMO_KNOWLEDGE_DOCUMENTS}
    assert len(categories) >= 5


def test_knowledge_base_has_merchant_scoped_documents():
    scoped = [d for d in DEMO_KNOWLEDGE_DOCUMENTS if d.merchant_scope]
    assert any(d.merchant_scope == "Nimbus Retail" for d in scoped)


def test_short_document_single_chunk():
    doc = _doc(content="A short document that fits in one chunk.")
    chunks = chunk_document(doc, max_chars=1000)
    assert len(chunks) == 1
    assert chunks[0].document_id == doc.id
    assert chunks[0].chunk_index == 0
    assert chunks[0].category == doc.category


def test_long_document_is_split_into_multiple_chunks():
    sentences = " ".join(
        f"Retry policy paragraph number {i} explains that failed payments "
        "should be handled carefully in this demo context." for i in range(20)
    )
    doc = _doc(id="doc::long", content=sentences)
    chunks = chunk_document(doc, max_chars=120, overlap_chars=20)
    assert len(chunks) > 1
    # chunks are ordered and non-empty
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.content for c in chunks)
    # all chunk content belongs to the source document
    assert all(set(c.content) <= set(f" {doc.content} ") for c in chunks)


def test_chunk_ids_are_unique():
    doc = _doc(id="doc::long", content=" ".join(f"sentence {i} here." for i in range(50)))
    chunks = chunk_document(doc, max_chars=60, overlap_chars=10)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_payload_contains_metadata():
    doc = _doc(id="doc::meta", merchant_scope="Acme", content="payment context sentence.")
    chunks = chunk_document(doc, max_chars=200)
    p = chunks[0].payload
    assert p["document_id"] == "doc::meta"
    assert p["merchant_scope"] == "Acme"
    assert p["category"] == "retry_limits"


def test_chunk_document_rejects_bad_params():
    with pytest.raises(DocumentError):
        chunk_document(_doc(), max_chars=0)
    with pytest.raises(DocumentError):
        chunk_document(_doc(id="x", content="   "), max_chars=100)


# ---------------------------------------------------------------------------
# Embedding abstraction
# ---------------------------------------------------------------------------

def test_embedding_dimension_and_determinism():
    emb = LocalHashEmbeddingProvider(dimension=64)
    v1 = emb.embed("retry the payment")
    v2 = emb.embed("retry the payment")
    assert len(v1) == 64
    assert v1 == v2
    assert all(isinstance(x, float) for x in v1)


def test_embedding_vectors_are_normalized():
    emb = LocalHashEmbeddingProvider(dimension=64)
    v = emb.embed("a phrase with several distinct words here")
    norm = np.linalg.norm(v)
    # Vectors are normalized then rounded to 6 decimals, so allow small slack.
    assert abs(norm - 1.0) < 1e-4


def test_embedding_batch_matches_single():
    emb = LocalHashEmbeddingProvider(dimension=64)
    batch = emb.embed_many(["hello world", "another payment"])
    assert [emb.embed("hello world"), emb.embed("another payment")] == batch
    assert len(batch) == 2


def test_embedding_rejects_empty_text():
    emb = LocalHashEmbeddingProvider(dimension=64)
    with pytest.raises(EmbeddingError):
        emb.embed("")
    with pytest.raises(EmbeddingError):
        emb.embed("   ")


def test_create_embedding_provider_unknown_raises():
    with pytest.raises(EmbeddingError):
        create_embedding_provider("no-such-provider", dimension=64)


def test_create_embedding_provider_factory():
    emb = create_embedding_provider("hash", dimension=32)
    assert isinstance(emb, LocalHashEmbeddingProvider)
    assert emb.dimension == 32


# ---------------------------------------------------------------------------
# Vector store (in-memory) behaviour
# ---------------------------------------------------------------------------

def test_inmemory_store_upsert_and_count():
    store = InMemoryVectorStore()
    store.create_collection("c", 4)
    store.upsert("c", [VectorPoint(id="a", vector=[1.0, 0, 0, 0], payload={"x": 1})])
    assert store.count("c") == 1


def test_inmemory_store_search_missing_collection_raises():
    store = InMemoryVectorStore()
    with pytest.raises(CollectionNotFoundError):
        store.search("missing", [1.0, 0, 0], 3)


# ---------------------------------------------------------------------------
# Retrieval result formatting
# ---------------------------------------------------------------------------

def test_format_result_structures_hits():
    raw = [
        {
            "id": "chunk-1",
            "score": 0.9,
            "payload": {
                "document_id": "doc1",
                "category": "retry_limits",
                "merchant_scope": "Nimbus Retail",
                "source": "synthetic-demo",
            },
            "content": "Network timeouts may be retried up to three times.",
        }
    ]
    result = format_result("retry limits", "Nimbus Retail", 1, raw)
    assert isinstance(result, RetrievalResult)
    assert result.query == "retry limits"
    assert result.hits[0].document_id == "doc1"
    assert result.hits[0].category == "retry_limits"
    assert result.hits[0].merchant_scope == "Nimbus Retail"
    assert result.hits[0].score == pytest.approx(0.9)


def test_format_result_clamps_scores():
    result = format_result("q", None, 5, [{"id": "x", "score": 5.0, "payload": {}, "content": ""}])
    assert result.hits[0].score == 1.0


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

def test_seed_knowledge_base_indexes_chunks():
    store = InMemoryVectorStore()
    emb = LocalHashEmbeddingProvider(dimension=128)
    count = seed_knowledge_base(store, emb, "kb", documents=[_doc()])
    assert count >= 1
    assert store.count("kb") == count


def test_seed_is_idempotent():
    store = InMemoryVectorStore()
    emb = LocalHashEmbeddingProvider(dimension=128)
    docs = [_doc(id="a"), _doc(id="b")]
    first = seed_knowledge_base(store, emb, "kb", documents=docs)
    second = seed_knowledge_base(store, emb, "kb", documents=docs)
    assert first == second
    assert store.count("kb") == second  # no duplicates after reseed


# ---------------------------------------------------------------------------
# Retriever behaviour + merchant filtering/scoping
# ---------------------------------------------------------------------------

def _seeded_service() -> RAGService:
    svc = _service()
    docs = [
        _doc(id="global::1", category="retry_limits",
             content="Global guidance: network timeouts may be retried up to three times."),
        _doc(id="nimbus::1", category="merchant_recovery_policy", merchant_scope="Nimbus Retail",
             content="Nimbus Retail: escalate high value failed payments to manual review."),
        _doc(id="vertex::1", category="merchant_recovery_policy", merchant_scope="Vertex Electronics",
             content="Vertex Electronics: prefer fresh payment links over blind retries."),
    ]
    seed_knowledge_base(svc.store, svc.embeddings, svc.collection, documents=docs)
    return svc


def test_retrieve_without_merchant_returns_global_context():
    svc = _seeded_service()
    result = svc.retrieve("network timeout retry", top_k=5)
    assert isinstance(result, RetrievalResult)
    assert result.top_k == 5
    assert result.merchant_id is None
    categories = {h.category for h in result.hits}
    assert categories


def test_retrieve_merchant_scoped_filters_on_merchant():
    svc = _seeded_service()
    result = svc.retrieve("refund retry payment", merchant_id="Nimbus Retail", top_k=5)
    assert result.merchant_id == "Nimbus Retail"
    assert result.hits
    # Only Nimbus Retail scoped docs (plus no global docs) should be returned.
    for h in result.hits:
        assert h.merchant_scope == "Nimbus Retail"


def test_retrieve_different_merchant_returns_different_results():
    svc = _seeded_service()
    a = svc.retrieve("payment context", merchant_id="Nimbus Retail", top_k=5)
    b = svc.retrieve("payment context", merchant_id="Vertex Electronics", top_k=5)
    ids_a = {h.document_id for h in a.hits}
    ids_b = {h.document_id for h in b.hits}
    assert "nimbus::1" in ids_a
    assert "vertex::1" in ids_b
    assert not (ids_a & ids_b)


def test_retrieve_hits_expose_metadata():
    svc = _seeded_service()
    result = svc.retrieve("merchant recovery policy", merchant_id="Nimbus Retail", top_k=5)
    assert result.hits
    h = result.hits[0]
    assert h.id and h.document_id and h.category and h.content
    assert 0.0 <= h.score <= 1.0
    assert h.source


def test_retrieve_empty_query_raises():
    svc = _seeded_service()
    with pytest.raises(RetrieverError):
        svc.retrieve("")
    with pytest.raises(RetrieverError):
        svc.retrieve("   ")


def test_retrieve_invalid_top_k_raises():
    svc = _seeded_service()
    with pytest.raises(RetrieverError):
        svc.retrieve("payment", top_k=0)
    with pytest.raises(RetrieverError):
        svc.retrieve("payment", top_k=-1)


# ---------------------------------------------------------------------------
# Error handling / robustness
# ---------------------------------------------------------------------------

def test_retriever_store_error_is_normalized():
    class BoomStore(InMemoryVectorStore):
        def search(self, *a, **k):
            raise RuntimeError("boom")

    emb = LocalHashEmbeddingProvider(dimension=64)
    retriever = Retriever(store=BoomStore(), embeddings=emb, collection="c")
    with pytest.raises(RetrieverError):
        retriever.retrieve("payment")


def test_retriever_embedding_error_is_normalized():
    class BoomEmbed(LocalHashEmbeddingProvider):
        def embed(self, text):
            raise EmbeddingError("no embeddings")

    store = InMemoryVectorStore()
    store.create_collection("c", 64)
    retriever = Retriever(store=store, embeddings=BoomEmbed(dimension=64), collection="c")
    with pytest.raises(RetrieverError):
        retriever.retrieve("payment")


def test_service_default_collection_from_settings():
    svc = RAGService(
        store=InMemoryVectorStore(),
        embeddings=LocalHashEmbeddingProvider(dimension=64),
    )
    assert svc.collection  # default collection name is non-empty
    assert svc.retriever.default_top_k >= 1
