"""SQLite-backed registry of uploaded documents.

Chroma owns the vectors; this table owns the human-facing metadata (original
filename, size, chunk count, created time) so the UI can list and delete
documents without touching the vector store.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Config

_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id           TEXT PRIMARY KEY,
    filename     TEXT NOT NULL,
    stored_name  TEXT NOT NULL,
    extension    TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    chunks       INTEGER NOT NULL DEFAULT 0,
    pages        INTEGER,
    status       TEXT NOT NULL DEFAULT 'ready',
    error        TEXT,
    created_at   TEXT NOT NULL
);
"""


class DocumentStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # -- writes ------------------------------------------------------------
    def create(
        self,
        *,
        filename: str,
        stored_name: str,
        extension: str,
        size_bytes: int,
    ) -> str:
        doc_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        with _LOCK, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents
                    (id, filename, stored_name, extension, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, filename, stored_name, extension, size_bytes, created_at),
            )
        return doc_id

    def finalize(
        self,
        doc_id: str,
        *,
        chunks: int,
        pages: int | None = None,
    ) -> None:
        with _LOCK, self._connect() as conn:
            conn.execute(
                "UPDATE documents SET chunks = ?, pages = ?, status = 'ready', error = NULL"
                " WHERE id = ?",
                (chunks, pages, doc_id),
            )

    def mark_failed(self, doc_id: str, error: str) -> None:
        with _LOCK, self._connect() as conn:
            conn.execute(
                "UPDATE documents SET status = 'failed', error = ? WHERE id = ?",
                (error[:1000], doc_id),
            )

    def delete(self, doc_id: str) -> sqlite3.Row | None:
        with _LOCK, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if row is not None:
                conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return row

    # -- reads -------------------------------------------------------------
    def list_all(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, doc_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        return dict(row) if row else None

    def exists(self, doc_id: str) -> bool:
        return self.get(doc_id) is not None


_store: DocumentStore | None = None


def get_doc_store() -> DocumentStore:
    global _store
    if _store is None:
        _store = DocumentStore(Config.DB_PATH)
    return _store
