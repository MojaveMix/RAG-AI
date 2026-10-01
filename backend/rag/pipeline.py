"""The RAG pipeline: ingest documents, retrieve context, answer questions."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from config import Config
from rag.chunking import build_chunks
from rag.loader import parse_bytes
from rag.vectorstore import get_store
from services.document_store import DocumentStore
from services.ollama_client import get_client

logger = logging.getLogger(__name__)

# Batching keeps embedding requests fast without overwhelming Ollama.
EMBED_BATCH_SIZE = 16


def _embed_documents(texts: list[str]) -> list[list[float]]:
    client = get_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        vectors.extend(client.embed(batch, prefix=Config.EMBED_DOC_PREFIX))
    return vectors


def ingest(data: bytes, filename: str, stored_name: str, doc_store: DocumentStore) -> dict[str, Any]:
    """Parse, chunk, embed and index an uploaded file.

    Raises ``EmptyDocument`` / ``UnsupportedFileType`` from the loader, or
    ``OllamaError`` if the embedding model is unavailable. In every failure case
    the document row is marked ``failed`` so the UI can show why.
    """
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    doc_id = doc_store.create(
        filename=filename,
        stored_name=stored_name,
        extension=extension,
        size_bytes=len(data),
    )

    try:
        parsed = parse_bytes(data, filename)

        base_metadata = {"document_id": doc_id, "filename": filename}
        if parsed.page_texts:
            # Page-aware: chunk each page separately so citations can name a page.
            chunks = []
            for page_number, page_text in enumerate(parsed.page_texts, start=1):
                if not page_text.strip():
                    continue
                chunks.extend(
                    build_chunks(
                        page_text,
                        chunk_size=Config.CHUNK_SIZE,
                        chunk_overlap=Config.CHUNK_OVERLAP,
                        base_metadata={**base_metadata, "page": page_number},
                    )
                )
        else:
            chunks = build_chunks(
                parsed.text,
                chunk_size=Config.CHUNK_SIZE,
                chunk_overlap=Config.CHUNK_OVERLAP,
                base_metadata=base_metadata,
            )

        if not chunks:
            raise ValueError("No usable text could be extracted from this file.")

        # Renumber globally so chunk_index is unique across the whole document.
        for position, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_index"] = position

        vectors = _embed_documents([chunk.text for chunk in chunks])

        payload = [
            {
                # Use the globally-renumbered chunk_index (set on line 77 above),
                # NOT chunk.index which resets to 1 for every page and causes
                # duplicate ChromaDB IDs on multi-page documents.
                "id": f"{doc_id}:{chunk.metadata['chunk_index']}",
                "text": chunk.text,
                "metadata": {
                    **chunk.metadata,
                    "extension": extension,
                },
            }
            for chunk in chunks
        ]
        get_store().add(document_id=doc_id, chunks=payload, embeddings=vectors)
        doc_store.finalize(doc_id, chunks=len(payload), pages=parsed.pages)
    except Exception as exc:  # noqa: BLE001 - surface the reason to the client
        logger.exception("Ingestion failed for %s", filename)
        doc_store.mark_failed(doc_id, str(exc))
        raise

    return doc_store.get(doc_id) or {"id": doc_id, "filename": filename}


def retrieve(
    question: str,
    *,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Embed the question and return the most similar chunks."""
    if document_ids is not None and not document_ids:
        return []

    embedding = get_client().embed_query(question)
    return get_store().query(
        embedding,
        n_results=top_k or Config.TOP_K,
        document_ids=document_ids or None,
    )


def format_sources(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shape retrieval hits into citation payloads for the frontend."""
    sources: list[dict[str, Any]] = []
    for position, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata") or {}
        sources.append(
            {
                "label": position,
                "filename": metadata.get("filename", "Unknown document"),
                "document_id": metadata.get("document_id", ""),
                "chunk_index": metadata.get("chunk_index"),
                "page": metadata.get("page"),
                "score": hit.get("score"),
                "excerpt": (hit.get("text") or "").strip(),
            }
        )
    return sources


def build_prompt(question: str, hits: list[dict[str, Any]]) -> str:
    """Render the numbered context block injected into the user message."""
    blocks = []
    for position, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata") or {}
        location = metadata.get("filename", "document")
        if metadata.get("page"):
            location = f"{location} (page {metadata['page']})"
        text = (hit.get("text") or "").strip()
        blocks.append(f"[{position}] Source: {location}\n{text}")

    return (
        "Context excerpts from the uploaded documents:\n\n"
        + "\n\n".join(blocks)
        + "\n\n---\n\n"
        f"Question: {question}\n"
        "Answer using only the context above, citing excerpts as [1], [2], etc."
    )


def build_messages(
    question: str,
    hits: list[dict[str, Any]],
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": Config.SYSTEM_PROMPT}
    ]

    for turn in (history or [])[-Config.MAX_HISTORY_TURNS * 2 :]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    if hits:
        messages.append({"role": "user", "content": build_prompt(question, hits)})
    else:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{question}\n\n"
                    "(No documents are currently uploaded. Let the user know they "
                    "should upload a document first.)"
                ),
            }
        )
    return messages


def answer_stream(
    question: str,
    *,
    document_ids: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield SSE-ready events: sources, then token deltas, then ``done``."""
    hits = retrieve(question, document_ids=document_ids)
    yield {"event": "sources", "data": format_sources(hits)}

    messages = build_messages(question, hits, history)
    try:
        for delta in get_client().chat_stream(messages, model=model):
            yield {"event": "delta", "data": delta}
    except Exception as exc:  # noqa: BLE001 - report mid-stream failures inline
        logger.exception("Streaming failed")
        yield {"event": "error", "data": str(exc)}
        return

    yield {"event": "done", "data": ""}
