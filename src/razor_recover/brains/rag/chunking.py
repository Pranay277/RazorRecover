"""Document chunking for the knowledge base.

Long documents are split into overlapping chunks so each vector-store point
carries a small, self-contained unit of context. Chunking is deterministic and
independent of embedding / storage so it is easy to unit test.
"""

from __future__ import annotations

from src.razor_recover.brains.rag.exceptions import DocumentError
from src.razor_recover.brains.rag.schemas import DocumentChunk, KnowledgeDocument

DEFAULT_MAX_CHARS = 500
DEFAULT_OVERLAP_CHARS = 60


def split_into_sentences(text: str) -> list[str]:
    """Naive sentence splitter that keeps abbreviations intact (roughly)."""
    normalized = text.replace("\n", " ").strip()
    if not normalized:
        return []
    parts = []
    current = ""
    for token in normalized.split(" "):
        current = f"{current} {token}".strip()
        if token.endswith((".", "!", "?")):
            parts.append(current)
            current = ""
    if current:
        parts.append(current)
    return [p.strip() for p in parts if p.strip()]


def chunk_document(
    doc: KnowledgeDocument,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[DocumentChunk]:
    """Split a knowledge document into ordered, overlapping chunks."""
    if max_chars <= 0 or overlap_chars < 0:
        raise DocumentError("Chunking requires max_chars > 0 and overlap >= 0.")
    if overlap_chars >= max_chars:
        overlap_chars = max(0, max_chars // 2)

    sentences = split_into_sentences(doc.content)
    if not sentences:
        raise DocumentError(f"Document {doc.id} has no embeddable content.")

    chunks: list[DocumentChunk] = []
    buffer = ""
    chunk_index = 0

    def flush() -> None:
        nonlocal buffer, chunk_index
        if buffer.strip():
            chunks.append(
                DocumentChunk(
                    id=f"{doc.id}::chunk{chunk_index:03d}",
                    document_id=doc.id,
                    content=buffer.strip(),
                    chunk_index=chunk_index,
                    category=doc.category,
                    merchant_scope=doc.merchant_scope,
                    source=doc.source,
                    tags=doc.tags,
                )
            )
            chunk_index += 1

    for sentence in sentences:
        if not buffer or (len(buffer) + len(sentence) + 1) <= max_chars:
            buffer = f"{buffer} {sentence}".strip() if buffer else sentence
            continue
        flush()
        # Carry trailing characters of the previous chunk for overlap.
        overlap = buffer[-overlap_chars:] if overlap_chars else ""
        buffer = f"{overlap} {sentence}".strip()
    flush()

    if not chunks:
        raise DocumentError(f"Document {doc.id} produced no chunks.")
    return chunks
