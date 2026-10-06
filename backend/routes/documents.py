"""Document upload / listing / deletion endpoints."""

from __future__ import annotations

import logging
import uuid

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from config import Config
from rag.loader import EmptyDocument, UnsupportedFileType
from rag.pipeline import ingest
from rag.vectorstore import get_store
from services.document_store import get_doc_store
from services.ollama_client import OllamaError, get_client

logger = logging.getLogger(__name__)

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _serialize(row: dict) -> dict:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "extension": row["extension"],
        "size_bytes": row["size_bytes"],
        "chunks": row["chunks"],
        "pages": row["pages"],
        "status": row["status"],
        "error": row["error"],
        "created_at": row["created_at"],
    }


@documents_bp.get("")
def list_documents():
    doc_store = get_doc_store()
    store = get_store()
    documents = []
    for row in doc_store.list_all():
        item = _serialize(row)
        item["indexed_chunks"] = store.count(row["id"])
        documents.append(item)
    return jsonify({"documents": documents})


@documents_bp.post("")
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request. Use the 'file' field."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected."}), 400

    original_name = file.filename
    base_name = original_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    extension = ("." + original_name.rsplit(".", 1)[-1].lower()) if "." in original_name else ""

    data = file.read()
    if not data:
        return jsonify({"error": "The uploaded file is empty."}), 400

    # Binary check helper
    is_known_ext = extension in Config.ALLOWED_EXTENSIONS
    is_known_file = base_name in getattr(Config, "ALLOWED_FILENAMES", set())
    sample = data[:4096]
    is_binary = b"\x00" in sample and not (data.startswith((b"\xff\xfe", b"\xfe\xff")))

    if not is_known_ext and not is_known_file and is_binary:
        return (
            jsonify(
                {
                    "error": (
                        f"'{original_name}' is a binary file and cannot be parsed as text or code. "
                        "Please upload source code, scripts, documents, or ZIP archives."
                    )
                }
            ),
            415,
        )

    client = get_client()
    if not client.is_running():
        return jsonify({"error": "Ollama is not reachable. Start it with `ollama serve`."}), 503
    if not client.has_model(Config.EMBED_MODEL):
        return (
            jsonify({"error": f"Embedding model '{Config.EMBED_MODEL}' is missing. Run: ollama pull {Config.EMBED_MODEL}"}),
            503,
        )

    # Prefix with a uuid so two uploads of the same filename never collide.
    safe_name = secure_filename(original_name) or f"upload{extension}"
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    stored_path = Config.UPLOAD_DIR / stored_name

    try:
        stored_path.write_bytes(data)
    except OSError as exc:
        logger.exception("Could not persist upload")
        return jsonify({"error": f"Could not save the upload: {exc}"}), 500

    try:
        row = ingest(data, original_name, stored_name, get_doc_store())
    except (EmptyDocument, UnsupportedFileType) as exc:
        stored_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 422
    except OllamaError as exc:
        stored_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:  # noqa: BLE001
        logger.exception("Upload failed")
        return jsonify({"error": f"Could not process the file: {exc}"}), 500

    payload = _serialize(row)
    payload["indexed_chunks"] = get_store().count(row["id"])
    return jsonify({"document": payload}), 201


@documents_bp.get("/<doc_id>")
def get_document(doc_id: str):
    row = get_doc_store().get(doc_id)
    if not row:
        return jsonify({"error": "Document not found."}), 404
    payload = _serialize(row)
    payload["indexed_chunks"] = get_store().count(doc_id)
    return jsonify({"document": payload})


@documents_bp.delete("/<doc_id>")
def delete_document(doc_id: str):
    doc_store = get_doc_store()
    row = doc_store.get(doc_id)
    if not row:
        return jsonify({"error": "Document not found."}), 404

    get_store().delete_document(doc_id)
    doc_store.delete(doc_id)

    try:
        (Config.UPLOAD_DIR / row["stored_name"]).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove stored file for %s", doc_id)

    return jsonify({"deleted": doc_id})
