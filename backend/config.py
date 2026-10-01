"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # --- Ollama -----------------------------------------------------------
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3:8b")
    EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

    # Nomic-style models expect task prefixes for best results. Leave empty for
    # models such as bge-m3 / mxbai-embed-large that must not be prefixed.
    EMBED_DOC_PREFIX = os.getenv("EMBED_DOC_PREFIX", "")
    EMBED_QUERY_PREFIX = os.getenv("EMBED_QUERY_PREFIX", "")

    # Qwen3 defaults to "thinking" mode which is slow for short RAG answers.
    LLM_THINK = os.getenv("LLM_THINK", "false").lower() in {"1", "true", "yes", "on"}
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_CONTEXT_WINDOW = _int_env("LLM_CONTEXT_WINDOW", 8192)
    MAX_HISTORY_TURNS = _int_env("MAX_HISTORY_TURNS", 6)

    # --- Storage ----------------------------------------------------------
    DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
    CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma")))
    DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "documents.db")))
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads")))
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_documents")

    # --- RAG --------------------------------------------------------------
    CHUNK_SIZE = _int_env("CHUNK_SIZE", 1200)
    CHUNK_OVERLAP = _int_env("CHUNK_OVERLAP", 200)
    TOP_K = _int_env("TOP_K", 5)

    # --- Uploads ----------------------------------------------------------
    MAX_CONTENT_LENGTH = _int_env("MAX_UPLOAD_MB", 32) * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}

    # --- CORS -------------------------------------------------------------
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    SYSTEM_PROMPT = (
        "You are a helpful assistant that answers questions about documents "
        "the user has uploaded.\n\n"
        "Rules:\n"
        "- Answer ONLY using the provided context excerpts.\n"
        "- If the context does not contain the answer, say exactly: "
        "\"I could not find that in the uploaded documents.\"\n"
        "- Never invent facts, numbers or citations.\n"
        "- When the answer depends on several excerpts, combine them and cite "
        "them like [1], [2].\n"
        "- Keep answers concise and well organised. Use short paragraphs or "
        "bullet lists.\n"
        "- Refer to sources by their excerpt label when helpful."
    )

    @classmethod
    def ensure_dirs(cls) -> None:
        for path in (cls.DATA_DIR, cls.CHROMA_DIR, cls.UPLOAD_DIR):
            path.mkdir(parents=True, exist_ok=True)
