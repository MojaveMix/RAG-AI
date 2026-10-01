"""ChromaDB vector store wrapper.

A single collection holds every uploaded document's chunks. Chunks are tagged
with ``document_id`` metadata so retrieval can be scoped to one document, a
handful of documents, or the whole library.
"""

from __future__ import annotations

import threading
from typing import Any

import chromadb
from chromadb.config import Settings

from config import Config


class VectorStore:
    def __init__(self, persist_dir: str | None = None, collection: str | None = None) -> None:
        persist_path = persist_dir or str(Config.CHROMA_DIR)
        self.collection_name = collection or Config.COLLECTION_NAME
        self._lock = threading.Lock()
        self._client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"hnsw:space": "cosine"},
        )

    # -- writes ------------------------------------------------------------
    def add(
        self,
        *,
        document_id: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        with self._lock:
            self._collection.upsert(
                ids=[chunk["id"] for chunk in chunks],
                documents=[chunk["text"] for chunk in chunks],
                embeddings=embeddings,
                metadatas=[chunk["metadata"] for chunk in chunks],
            )

    def delete_document(self, document_id: str) -> None:
        with self._lock:
            self._collection.delete(where={"document_id": document_id})

    def delete_all(self) -> None:
        with self._lock:
            self._collection.delete(where={"document_id": {"$ne": ""}})

    # -- reads -------------------------------------------------------------
    def query(
        self,
        embedding: list[float],
        *,
        n_results: int,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        where: dict[str, Any] | None = None
        if document_ids:
            where = {"document_id": {"$in": document_ids}}

        with self._lock:
            result = self._collection.query(
                query_embeddings=[embedding],
                n_results=max(1, n_results),
                where=where,
                include=["documents", "metadatas", "distances"],
            )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        hits: list[dict[str, Any]] = []
        for position, text in enumerate(documents):
            hits.append(
                {
                    "text": text or "",
                    "metadata": metadatas[position] or {},
                    # Cosine distance -> similarity in [0, 1].
                    "score": round(1.0 - float(distances[position]), 4)
                    if position < len(distances)
                    else None,
                }
            )
        return hits

    def count(self, document_id: str | None = None) -> int:
        # Chroma's Collection.count() takes no `where` filter, so count via get().
        with self._lock:
            if not document_id:
                return self._collection.count()
            result = self._collection.get(
                where={"document_id": document_id},
                include=[],  # ids only; skips loading documents/embeddings
            )
            return len(result.get("ids") or [])


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
