"""Seed the synthetic/demo knowledge base into the vector store.

Idempotent: re-running recreates the target collection and re-indexes from
scratch. Uses the RAG layer's configured provider + store (Qdrant by default).

Usage:
    python scripts/seed_vector_db.py
    python scripts/seed_vector_db.py --provider hash --dim 256 --collection my_kb
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project ``src`` tree is importable when run as a plain script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.razor_recover.brains.rag.embeddings import create_embedding_provider
from src.razor_recover.brains.rag.exceptions import RAGError
from src.razor_recover.brains.rag.seeder import seed_knowledge_base
from src.razor_recover.brains.rag.vector_store import create_vector_store
from src.razor_recover.config import get_settings
from src.razor_recover.core.logger import configure_logging, get_logger

logger = get_logger("script.seed_vector_db")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Seed the RazorRecover knowledge base.")
    p.add_argument("--url", type=str, default=None, help="Vector-store URL (default: settings).")
    p.add_argument("--collection", type=str, default=None, help="Collection name.")
    p.add_argument("--provider", type=str, default=None, help="Embedding provider (hash|ollama).")
    p.add_argument("--model", type=str, default=None, help="Embedding model for the provider.")
    p.add_argument("--dim", type=int, default=None, help="Embedding dimension.")
    p.add_argument("--storage", type=str, default="qdrant",
                   help="Vector-store backend (qdrant|inmemory).")
    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    settings = get_settings()

    url = args.url or settings.qdrant_url
    collection = args.collection or settings.qdrant_collection
    provider = args.provider or settings.rag_embedding_provider
    model = args.model or settings.rag_embedding_model
    dim = args.dim or settings.rag_embedding_dim

    store = create_vector_store(url, storage=args.storage)
    embeddings = create_embedding_provider(
        provider=provider, dimension=dim, model=model, base_url=settings.ollama_url
    )

    if not store.ping():
        logger.error("Vector store at %s is not reachable.", url)
        return 1

    try:
        indexed = seed_knowledge_base(store, embeddings, collection)
    except RAGError as exc:
        logger.error("Failed to seed knowledge base: %s", exc)
        return 1

    total = store.count(collection)
    print(f"Seeded {indexed} chunks into collection '{collection}' ({total} total points).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
