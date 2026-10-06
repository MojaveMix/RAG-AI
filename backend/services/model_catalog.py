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
RECOMMENDED_ANALYSIS_CHAT: list[dict[str, str]] = [
    {
        "model": "qwen3:8b",
        "label": "Qwen3 8B",
        "blurb": "Best all-rounder for document analysis. Multilingual (Arabic, French, English), reliable [1] citations.",
    },
    {
        "model": "gemma3:12b",
        "label": "Gemma 3 12B",
        "blurb": "Excellent multilingual prose (Arabic, French, English). Ideal for synthesis & summaries.",
    },
    {
        "model": "qwen3.5:9b",
        "label": "Qwen3.5 9B",
        "blurb": "Newer Qwen with very long context and strong multilingual reasoning.",
    },
    {
        "model": "aya-expanse:8b",
        "label": "Aya Expanse 8B",
        "blurb": "Built for multilingual use: 23 languages incl. Arabic, French, English.",
    },
    {
        "model": "mistral-nemo:12b",
        "label": "Mistral Nemo 12B",
        "blurb": "Very good French and European languages, large context window.",
    },
    {
        "model": "deepseek-r1:8b",
        "label": "DeepSeek R1 8B",
        "blurb": "Reasons deeply before answering documents. Thinking tokens handled automatically.",
    },
    {
        "model": "llama3.2:3b",
        "label": "Llama 3.2 3B",
        "blurb": "Fastest option. Weaker on multi-source synthesis and non-English languages.",
    },
    {
        "model": "qwen2.5:7b",
        "label": "Qwen2.5 7B",
        "blurb": "Solid multilingual fallback for document Q&A.",
    },
]

RECOMMENDED_CODE_CHAT: list[dict[str, str]] = [
    {
        "model": "qwen2.5-coder:7b",
        "label": "Qwen 2.5 Coder 7B",
        "blurb": "World-class coding engine. Generates full implementations, SQL schemas, refactors, and tests.",
    },
    {
        "model": "deepseek-coder:6.7b",
        "label": "DeepSeek Coder 6.7B",
        "blurb": "Trained on 2T code tokens. Highly capable code generation and bug fixing.",
    },
    {
        "model": "codellama:7b",
        "label": "Code Llama 7B",
        "blurb": "Meta's dedicated code model for Python, C++, Java, JS and algorithms.",
    },
    {
        "model": "qwen2.5-coder:1.5b",
        "label": "Qwen 2.5 Coder 1.5B",
        "blurb": "Fast, lightweight code generation model.",
    },
    {
        "model": "qwen2.5-coder:14b",
        "label": "Qwen 2.5 Coder 14B",
        "blurb": "Large-scale code powerhouse for complex architectural and full-stack tasks.",
    },
]

RECOMMENDED_CHAT: list[dict[str, str]] = RECOMMENDED_ANALYSIS_CHAT + RECOMMENDED_CODE_CHAT

_CODE_HINTS = ("coder", "code", "codellama", "starcoder", "deepseek-coder", "codegeex")


def is_code_model(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in _CODE_HINTS)

RECOMMENDED_EMBED: list[dict[str, str]] = [
    {
        "model": "bge-m3",
        "label": "BGE-M3",
        "blurb": "Best multilingual retrieval: 100+ languages incl. Arabic, French, English, and cross-language search. 1024-dim.",
    },
    {
        "model": "qwen3-embedding:0.6b",
        "label": "Qwen3 Embedding 0.6B",
        "blurb": "Multilingual, strong quality per GB. Needs a re-index after switching.",
    },
    {
        "model": "nomic-embed-text",
        "label": "Nomic Embed Text",
        "blurb": "768-dim, long context. English-centric; weaker for Arabic/French.",
    },
    {
        "model": "mxbai-embed-large",
        "label": "Mxbai Embed Large",
        "blurb": "Solid English-only retrieval, 1024-dim.",
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
            info["is_code"] = is_code_model(name)
            info["category"] = "code" if info["is_code"] else "analysis"
            chat.append(info)

    # Smallest first: a local box rarely has room for several 30B models, and
    # the fastest model is the most pleasant default on CPU.
    chat.sort(key=lambda item: (item["size_gb"] is None, item["size_gb"] or 0))
    embedding.sort(key=lambda item: (item["size_gb"] is None, item["size_gb"] or 0))

    chat_names = [item["name"] for item in chat]
    embed_names = [item["name"] for item in embedding]

    recommended_chat = _curated(chat_names, RECOMMENDED_CHAT)
    recommended_code = _curated(chat_names, RECOMMENDED_CODE_CHAT)
    recommended_analysis = _curated(chat_names, RECOMMENDED_ANALYSIS_CHAT)

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

    code_names = [item["name"] for item in chat if item["is_code"]]
    analysis_names = [item["name"] for item in chat if not item["is_code"]]

    default_code = _pick_default(code_names, recommended_code) or _pick_default(chat_names, recommended_chat)
    default_analysis = _pick_default(analysis_names, recommended_analysis) or _pick_default(chat_names, recommended_chat)

    return {
        "chat": chat,
        "code_chat": [item for item in chat if item["is_code"]],
        "analysis_chat": [item for item in chat if not item["is_code"]],
        "embedding": embedding,
        "recommended_chat": recommended_chat,
        "suggested_chat": _suggested(RECOMMENDED_CHAT, chat_names),
        "recommended_code": recommended_code,
        "suggested_code": _suggested(RECOMMENDED_CODE_CHAT, chat_names),
        "recommended_analysis": recommended_analysis,
        "suggested_analysis": _suggested(RECOMMENDED_ANALYSIS_CHAT, chat_names),
        "recommended_embed": _curated(embed_names, RECOMMENDED_EMBED),
        "suggested_embed": _suggested(RECOMMENDED_EMBED, embed_names),
        "default_chat": _pick_default(chat_names, recommended_chat),
        "default_code_chat": default_code,
        "default_analysis_chat": default_analysis,
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
