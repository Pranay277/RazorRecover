"""Vector-store abstraction for the RAG layer.

Retrieval and seeding depend only on the :class:`VectorStore` interface, so the
underlying store (Qdrant today) can be swapped without touching the rest of the
RAG layer. Provider exceptions are normalized to :class:`VectorStoreError`.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from razor_recover.brains.rag.exceptions import (
    CollectionNotFoundError,
    VectorStoreError,
)
from razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.rag.vector_store")

# Fixed namespace so a given chunk id maps to a stable UUID (idempotent seeding).
_POINT_NS = uuid.UUID("4f8b1a90-2c3d-4e5f-9a7b-1c2d3e4f5a6b")


def _qdr_point_id(uid: str) -> str | uuid.UUID:
    """Map an application point id to a Qdrant-valid id (UUID)."""
    try:
        return str(uuid.UUID(str(uid)))
    except (ValueError, AttributeError):
        return str(uuid.uuid5(_POINT_NS, str(uid)))


@dataclass(frozen=True)
class VectorPoint:
    """A single vector-store record (payload carries chunk metadata)."""

    id: str
    vector: list[float]
    payload: Mapping[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """Contract implemented by concrete vector stores."""

    @abstractmethod
    def ping(self) -> bool: ...

    @abstractmethod
    def collection_exists(self, name: str) -> bool: ...

    @abstractmethod
    def create_collection(self, name: str, dimension: int) -> None: ...

    @abstractmethod
    def delete_collection(self, name: str) -> None: ...

    @abstractmethod
    def upsert(self, collection: str, points: list[VectorPoint]) -> int: ...

    @abstractmethod
    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def count(self, collection: str) -> int: ...


class InMemoryVectorStore(VectorStore):
    """Deterministic, network-free store used for unit tests and demos.

    Implements cosine similarity + exact (equality) payload filtering so the
    retriever behaves identically to the Qdrant-backed store.
    """

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, VectorPoint]] = {}

    def ping(self) -> bool:
        return True

    def collection_exists(self, name: str) -> bool:
        return name in self._collections

    def create_collection(self, name: str, dimension: int) -> None:
        self._collections.setdefault(name, {})

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)

    def upsert(self, collection: str, points: list[VectorPoint]) -> int:
        if collection not in self._collections:
            raise CollectionNotFoundError(f"Collection {collection!r} does not exist.")
        for p in points:
            self._collections[collection][p.id] = p
        return len(points)

    def _matches(self, payload: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        return all(payload.get(k) == v for k, v in filters.items())

    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if collection not in self._collections:
            raise CollectionNotFoundError(f"Collection {collection!r} does not exist.")
        query = np.asarray(query_vector, dtype=np.float64)
        query_norm = np.linalg.norm(query) or 1.0
        scored = []
        for point in self._collections[collection].values():
            if filters:
                to_check = {"merchant_scope": point.payload.get("merchant_scope")}
                if not self._matches(to_check, filters):
                    continue
            vec = np.asarray(point.vector, dtype=np.float64)
            norm = np.linalg.norm(vec)
            similarity = (float(np.dot(query, vec)) / (query_norm * norm)) if norm else 0.0
            scored.append((point, similarity))
        scored.sort(key=lambda t: t[1], reverse=True)
        return [
            {
                "id": p.id,
                "score": float(similarity),
                "payload": dict(p.payload),
                "content": p.payload.get("content", ""),
            }
            for p, similarity in scored[:top_k]
        ]

    def count(self, collection: str) -> int:
        return len(self._collections.get(collection, {}))


class QdrantVectorStore(VectorStore):
    """Qdrant-backed vector store."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        **client_kwargs,
    ) -> None:
        from qdrant_client import QdrantClient

        self._url = url
        self._client = QdrantClient(url=url, api_key=api_key, **client_kwargs)

    @classmethod
    def from_client(cls, client) -> "QdrantVectorStore":
        """Wrap an existing QdrantClient (e.g. a test one)."""
        store = cls.__new__(cls)
        store._url = ""
        store._client = client
        return store

    @staticmethod
    def _wrap(exc: Exception, context: str) -> VectorStoreError:
        return VectorStoreError(f"Qdrant {context} failed: {exc}")

    def ping(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception as exc:
            logger.warning("Qdrant ping failed: %s", exc)
            return False

    def collection_exists(self, name: str) -> bool:
        try:
            return any(c.name == name for c in self._client.get_collections().collections)
        except Exception as exc:
            raise self._wrap(exc, "list-collections") from exc

    def create_collection(self, name: str, dimension: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        try:
            if self.collection_exists(name):
                self._client.delete_collection(collection_name=name)
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection %r (dim=%d)", name, dimension)
        except Exception as exc:
            raise self._wrap(exc, "create-collection") from exc

    def delete_collection(self, name: str) -> None:
        try:
            if self.collection_exists(name):
                self._client.delete_collection(collection_name=name)
                logger.info("Deleted Qdrant collection %r", name)
        except Exception as exc:
            raise self._wrap(exc, "delete-collection") from exc

    def upsert(self, collection: str, points: list[VectorPoint]) -> int:
        from qdrant_client.models import PointStruct

        if not points:
            return 0
        try:
            self._client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=_qdr_point_id(p.id),
                        vector=p.vector,
                        payload=dict(p.payload),
                    )
                    for p in points
                ],
            )
            return len(points)
        except Exception as exc:
            raise self._wrap(exc, "upsert") from exc

    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        try:
            qfilter = None
            if filters:
                qfilter = Filter(
                    must=[
                        FieldCondition(
                            key=k, match=MatchValue(value=v)
                        )
                        for k, v in filters.items()
                    ]
                )
            response = self._client.query_points(
                collection_name=collection,
                query=query_vector,
                limit=top_k,
                query_filter=qfilter,
                with_payload=True,
            )
            hits = response.points if response else []
            return [
                {
                    "id": hit.id,
                    "score": float(hit.score),
                    "payload": dict(hit.payload or {}),
                    "content": (hit.payload or {}).get("content", ""),
                }
                for hit in hits
            ]
        except Exception as exc:
            raise self._wrap(exc, "search") from exc

    def count(self, collection: str) -> int:
        try:
            return self._client.count(collection_name=collection, exact=True).count
        except Exception as exc:
            raise self._wrap(exc, "count") from exc


def create_vector_store(
    url: str,
    *,
    storage: str = "qdrant",
) -> VectorStore:
    """Factory for a concrete vector store chosen by configuration."""
    name = (storage or "qdrant").lower().strip()
    if name in ("inmemory", "memory", "local"):
        return InMemoryVectorStore()
    if name == "qdrant":
        return QdrantVectorStore(url=url)
    raise VectorStoreError(f"Unknown vector store: {storage!r}")
