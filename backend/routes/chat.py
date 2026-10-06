"""Chat endpoint that streams answers over Server-Sent Events."""

from __future__ import annotations

import json
import logging

from flask import Blueprint, Response, jsonify, request

from config import Config
from rag.pipeline import answer_stream
from services.document_store import get_doc_store
from services.model_catalog import list_models
from services.ollama_client import OllamaError, get_client

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api")


def _sse(event: str, data) -> str:
    payload = data if isinstance(data, str) else json.dumps(data)
    # Every line needs its own `data:` prefix: a bare newline inside the payload
    # would otherwise terminate the frame early and corrupt the stream.
    body = "".join(f"data: {line}\n" for line in payload.split("\n"))
    return f"event: {event}\n{body}\n"


@chat_bp.get("/models")
def models():
    """Installed Ollama models, split by capability, with a recommended default."""
    client = get_client()
    if not client.is_running():
        return jsonify({"error": "Ollama is not reachable. Start it with `ollama serve`."}), 503
    return jsonify(list_models())


@chat_bp.get("/health")
def health():
    client = get_client()
    running = client.is_running()
    models = client.list_models() if running else []
    return jsonify(
        {
            "status": "ok" if running else "degraded",
            "ollama": {
                "running": running,
                "host": Config.OLLAMA_HOST,
                "chat_model": Config.CHAT_MODEL,
                "chat_model_ready": client.has_model(Config.CHAT_MODEL) if running else False,
                "embed_model": Config.EMBED_MODEL,
                "embed_model_ready": client.has_model(Config.EMBED_MODEL) if running else False,
                "installed_models": models,
            },
            "documents": len(get_doc_store().list_all()),
        }
    )


@chat_bp.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "A 'question' is required."}), 400

    document_ids = payload.get("document_ids")
    if document_ids is not None and not isinstance(document_ids, list):
        return jsonify({"error": "'document_ids' must be a list."}), 400

    history = payload.get("history") or []
    if not isinstance(history, list):
        return jsonify({"error": "'history' must be a list."}), 400

    # The UI sends the model picked in the selector; fall back to the configured
    # default so direct API callers keep working.
    model = payload.get("model") or Config.CHAT_MODEL
    if not isinstance(model, str):
        return jsonify({"error": "'model' must be a string."}), 400

    client = get_client()
    if not client.is_running():
        return jsonify({"error": "Ollama is not reachable. Start it with `ollama serve`."}), 503
    if not client.has_model(model):
        return (
            jsonify(
                {"error": f"Model '{model}' is not installed. Run: ollama pull {model}"}
            ),
            503,
        )

    # Drop ids that no longer exist so a stale UI selection cannot 500 later.
    # An empty list or None means search across all documents.
    known = {row["id"] for row in get_doc_store().list_all()}
    valid_ids = [doc_id for doc_id in document_ids if doc_id in known] if document_ids else None


    mode = str(payload.get("mode") or "code").lower()
    if mode not in {"code", "analysis"}:
        mode = "code"

    def generate() -> Response:
        try:
            for event in answer_stream(
                question, document_ids=valid_ids, history=history, model=model, mode=mode
            ):
                yield _sse(event["event"], event["data"])
        except OllamaError as exc:
            logger.warning("Chat stream aborted: %s", exc)
            yield _sse("error", str(exc))
        except Exception as exc:  # noqa: BLE001 - never leave the stream hanging
            logger.exception("Unexpected streaming error")
            yield _sse("error", f"Unexpected server error: {exc}")

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
