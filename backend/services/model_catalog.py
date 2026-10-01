"""Discovery and classification of locally installed Ollama models.

The UI needs more than a list of names to be useful: it has to know which
models can answer questions (chat), which ones can embed text, how big they
are, and which are a sensible default for grounded document Q&A. Ollama's
``/api/tags`` only reports name/size/details, so capability detection here is
best-effort and every field degrades gracefully when unknown.
"""

from __future__ import annotations

import re
from typing import Any

from services.ollama_client import get_client

# --- Curated shortlist ---------------------------------------------------
# Ordered best-first for document Q&A on a single local machine. These are
# suggestions only: any installed chat model can be picked in the UI.
RECOMMENDED_CHAT: list[dict[str, str]] = [
    {
        "model": "qwen3:8b",
        "label": "Qwen3 8B",
        "blurb": "Best all-rounder here. Strong instruction following, reliable [1] citations.",
    },
    {
        "model": "gemma3:12b",
        "label": "Gemma 3 12B",
        "blurb": "Smoother prose than Qwen3 at 12B. Good for long summaries.",
    },
    {
        "model": "llama3.2:3b",
        "label": "Llama 3.2 3B",
        "blurb": "Fastest option. Weaker on multi-source synthesis, but very quick.",
    },
    {
        "model": "mistral-nemo:12b",
        "label": "Mistral Nemo 12B",
        "blurb": "Large context window. Useful when several long documents are selected.",
    },
    {
        "model": "deepseek-r1:8b",
        "label": "DeepSeek R1 8B",
        "blurb": "Reasons before answering. Slower; thinking tokens are stripped from the reply.",
    },
    {
        "model": "qwen2.5:7b",
        "label": "Qwen2.5 7B",
        "blurb": "Solid fallback if you already have it. No thinking mode to disable.",
    },
]

RECOMMENDED_EMBED: list[dict[str, str]] = [
    {
        "model": "qwen3-embedding:0.6b",
        "label": "Qwen3 Embedding 0.6B",
        "blurb": "Best retrieval quality per GB. Needs a re-index after switching.",
    },
    {
        "model": "nomic-embed-text",
        "label": "Nomic Embed Text",
        "blurb": "768-dim, long context, the project default.",
    },
    {
        "model": "bge-m3",
        "label": "BGE-M3",
        "blurb": "Strong multilingual retrieval, 1024-dim.",
    },
    {
        "model": "mxbai-embed-large",
        "label": "Mxbai Embed Large",
        "blurb": "Solid English retrieval, 1024-dim.",
    },
]

# Substrings that mark a model as an embedding model when Ollama does not
# advertise capabilities (older servers omit the "embedding" flag).
_EMBED_HINTS = (
    "embed",
    "bge",
    "gte-",
    "gte-",
    "e5-",
    "minilm",
    "mxbai",
    "arctic-embed",
    "nomic-bert",
    "lab embeddings",
    "granite-embedding",
)

# Families that are embedding-only even though the name may not say so.
_EMBED_FAMILIES = {"nomic-bert", "bert", "xlm-roberta"}


def _norm(model: str) -> str:
    """Strip the tag: ``qwen3:8b`` -> ``qwen3``, ``gpt-oss:20b`` -> ``gpt-oss``."""
    return model.split(":")[0].strip().lower()


def _size_gb(size_bytes: int | None) -> float | None:
    if not isinstance(size_bytes, int) or size_bytes <= 0:
        return None
    return round(size_bytes / (1024**3), 1)


def _is_embedding(name: str, details: dict[str, Any], capabilities: list[str]) -> bool:
    if "embedding" in capabilities:
        return True
    if "completion" in capabilities or "chat" in capabilities:
        return False
    lowered = name.lower()
    if any(hint in lowered for hint in _EMBED_HINTS):
        return True
    family = str(details.get("family") or "").lower()
    return family in _EMBED_FAMILIES


def _parameter_label(name: str, details: dict[str, Any]) -> str | None:
    """Prefer the advertised parameter size, else parse the tag (``:8b``)."""
    advertised = details.get("parameter_size")
    if isinstance(advertised, str) and advertised.strip():
        return advertised.strip().upper()
    match = re.search(r":(\d+(?:\.\d+)?)b", name, re.IGNORECASE)
    return f"{match.group(1).upper()}B" if match else None


def _curated(models: list[str], recommendations: list[dict[str, str]]) -> list[dict[str, str]]:
    """Attach curated labels/blurbs to recommended models that are installed."""
    out = []
    for entry in recommendations:
        if any(_norm(name) == _norm(entry["model"]) for name in models):
            out.append({**entry, "installed": True})
    return out


def _suggested(recommendations: list[dict[str, str]], models: list[str]) -> list[dict[str, str]]:
    """Curated entries that are not installed, with the pull command to get them."""
    out = []
    for entry in recommendations:
        if not any(_norm(name) == _norm(entry["model"]) for name in models):
            out.append({**entry, "installed": False, "pull": f"ollama pull {entry['model']}"})
    return out


def list_models() -> dict[str, Any]:
    """Return chat/embedding models grouped for the UI, with a chosen default.

    Shape::

        {
          "chat": [{name, size_gb, parameters, family, quantization,
                    context_length, default, recommended}],
          "embedding": [...],
          "recommended_chat": [...], "suggested_chat": [...],
          "recommended_embed": [...], "suggested_embed": [...],
          "default_chat": "...", "default_embed": "..."
        }
    """
    client = get_client()
    raw_entries = client.list_model_entries()

    chat: list[dict[str, Any]] = []
    embedding: list[dict[str, Any]] = []

    for raw in raw_entries:
        name = (raw.get("name") or raw.get("model") or "").strip()
        if not name:
            continue
        details = dict(raw.get("details") or {})

        # Recent Ollama reports capabilities straight from /api/tags; only pay
        # for a /api/show round-trip when it does not.
        capabilities = [str(c) for c in (raw.get("capabilities") or [])]
        if not capabilities:
            capabilities = [str(c) for c in (client.model_details(name).get("capabilities") or [])]

        merged_details = {**details, **{k: v for k, v in (raw.get("details") or {}).items()}}
        remote = bool(raw.get("remote_model"))

        info = {
            "name": name,
            # A cloud model is a few hundred bytes of manifest, so the on-disk
            # size is meaningless; flag it instead of reporting "0.0 GB".
            "size_gb": None if remote else _size_gb(raw.get("size")),
            "parameters": _parameter_label(name, merged_details),
            "family": merged_details.get("family") or None,
            "quantization": merged_details.get("quantization_level") or None,
            "remote": remote,
            "modified_at": raw.get("modified_at"),
        }

        if _is_embedding(name, merged_details, capabilities):
            embedding.append(info)
        else:
            # /api/tags carries context_length on newer servers; fall back to
            # /api/show, and accept None when neither knows.
            context_length = details.get("context_length")
            if not context_length:
                context_length = client.context_length(name)
            if context_length:
                info["context_length"] = context_length
            chat.append(info)

    # Smallest first: a local box rarely has room for several 30B models, and
    # the fastest model is the most pleasant default on CPU.
    chat.sort(key=lambda item: (item["size_gb"] is None, item["size_gb"] or 0))
    embedding.sort(key=lambda item: (item["size_gb"] is None, item["size_gb"] or 0))

    chat_names = [item["name"] for item in chat]
    embed_names = [item["name"] for item in embedding]

    recommended_chat = _curated(chat_names, RECOMMENDED_CHAT)
    for item in chat:
        match = next(
            (entry for entry in recommended_chat if _norm(entry["model"]) == _norm(item["name"])),
            None,
        )
        item["recommended"] = bool(match)
        item["blurb"] = match["blurb"] if match else None

    for item in embedding:
        match = next(
            (
                entry
                for entry in _curated(embed_names, RECOMMENDED_EMBED)
                if _norm(entry["model"]) == _norm(item["name"])
            ),
            None,
        )
        item["recommended"] = bool(match)
        item["blurb"] = match["blurb"] if match else None

    return {
        "chat": chat,
        "embedding": embedding,
        "recommended_chat": recommended_chat,
        "suggested_chat": _suggested(RECOMMENDED_CHAT, chat_names),
        "recommended_embed": _curated(embed_names, RECOMMENDED_EMBED),
        "suggested_embed": _suggested(RECOMMENDED_EMBED, embed_names),
        "default_chat": _pick_default(chat_names, recommended_chat),
        "default_embed": _pick_default(embed_names, _curated(embed_names, RECOMMENDED_EMBED)),
    }


def _pick_default(names: list[str], recommended: list[dict[str, str]]) -> str | None:
    """First recommended model, else the smallest installed one.

    Returns the name Ollama actually reports (with its tag), not the curated
    spelling, so the value can be passed straight back to ``/api/chat``.
    """
    for entry in recommended:
        match = next((name for name in names if _norm(name) == _norm(entry["model"])), None)
        if match:
            return match
    return names[0] if names else None
