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
    EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")

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
    COLLECTION_NAME = os.getenv(
        "COLLECTION_NAME",
        f"rag_{os.getenv('EMBED_MODEL', 'bge-m3').replace(':', '_').replace('-', '_')}",
    )

    # --- RAG --------------------------------------------------------------
    CHUNK_SIZE = _int_env("CHUNK_SIZE", 1200)
    CHUNK_OVERLAP = _int_env("CHUNK_OVERLAP", 200)
    TOP_K = _int_env("TOP_K", 5)

    # --- Uploads ----------------------------------------------------------
    MAX_CONTENT_LENGTH = _int_env("MAX_UPLOAD_MB", 32) * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        # Documents & Notes
        ".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".rst", ".rtf", ".log",
        # Web & Frontend
        ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
        ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".d.ts",
        ".vue", ".svelte", ".astro",
        # Python & Data Science
        ".py", ".pyw", ".ipynb",
        # Systems & Compiled
        ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh",
        ".cs", ".java", ".kt", ".kts", ".scala",
        ".go", ".rs", ".swift", ".dart",
        # Scripting & Backend
        ".rb", ".php", ".lua", ".pl", ".pm", ".perl", ".r",
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
        # Data, Schemas & Config
        ".json", ".jsonc", ".yaml", ".yml", ".toml", ".xml", ".csv", ".tsv",
        ".sql", ".cql", ".graphql", ".gql", ".prisma",
        ".env", ".ini", ".cfg", ".conf", ".properties",
        ".dockerfile", ".containerfile", ".gradle", ".cmake", ".proto",
        # Archives
        ".zip",
    }

    # Common extensionless text / code filenames to accept automatically
    ALLOWED_FILENAMES = {
        "dockerfile", "makefile", "procfile", "gemfile", "jenkinsfile",
        "vagrantfile", "docker-compose.yml", "docker-compose.yaml",
        ".gitignore", ".dockerignore", ".env", ".env.example", "license", "readme"
    }

    # --- CORS -------------------------------------------------------------
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    ANALYSIS_SYSTEM_PROMPT = (
        "You are a helpful, multilingual assistant that answers questions about documents "
        "the user has uploaded. Documents and questions may be in any language "
        "(such as English, French, Arabic, Spanish, etc.).\n\n"
        "Rules:\n"
        "- STRICT LANGUAGE RULE: Always answer in the EXACT SAME language as the user's question. "
        "If the question is in English, reply in English. If the question is in French, reply in French. "
        "If the question is in Arabic, reply in Arabic. Never reply in a different language even if "
        "the source context excerpts are written in another language.\n"
        "- Answer ONLY using the provided context excerpts.\n"
        "- If the context does not contain the answer, state clearly that you could not find the "
        "information in the uploaded documents, written in the same language as the question.\n"
        "- Never invent facts, numbers, or citations.\n"
        "- When the answer depends on several excerpts, combine them and cite them like [1], [2].\n"
        "- Keep answers concise and well organised. Use short paragraphs or bullet lists.\n"
        "- Refer to sources by their excerpt label when helpful."
    )

    CODE_SYSTEM_PROMPT = (
        "You are RAG Code AI, an expert autonomous software engineer and AI coding assistant "
        "inspired by OpenAI Codex and Claude Code. You possess world-class expertise in software architecture, "
        "algorithms, full-stack development, devops, database design, and all programming languages.\n\n"
        "Core Capabilities & Rules:\n"
        "1. Complete Implementations: Write full, production-ready, clean, secure, and syntactically valid code. "
        "Never use lazy shortcuts like '// TODO: implement later', '// ... rest of code ...', or omit logic unless requested. "
        "Provide everything needed to run or integrate the code.\n"
        "2. Codebase Context: When uploaded code files or excerpts are provided in the context, deeply inspect their "
        "architecture, coding conventions, exported functions, classes, and types. Reference source files using tags like [1], [2] "
        "when explaining existing logic or integrating new code.\n"
        "3. DATA SYNTHESIS & SCHEMA GENERATION: When the user asks to generate SQL queries, database tables, schemas, "
        "models, APIs, or scripts based on data, locations, tables, or entities extracted from the uploaded documents "
        "(e.g. lists of regions, cities, departments, users, numbers), you MUST synthesize and write the complete SQL/code "
        "structures using the document data. NEVER refuse with 'the document does not contain SQL queries' or 'queries not found'—your job is to CREATE "
        "the code/queries that model and store that information!\n"
        "4. Standalone Generation: If no files are uploaded or the user asks for a new utility, component, or algorithm, "
        "immediately generate the optimal, modern solution without demanding file uploads.\n"
        "5. Fenced Code Blocks: Always format code within markdown fenced code blocks with the exact language identifier "
        "(e.g. ```sql, ```python, ```typescript, ```javascript, ```go, ```rust, ```bash, etc.).\n"
        "6. Technical Excellence: Explain architectural decisions, handle edge cases, include proper error handling, "
        "and provide testing or execution instructions when helpful."
    )

    # Backward-compatible alias
    SYSTEM_PROMPT = ANALYSIS_SYSTEM_PROMPT


    @classmethod
    def ensure_dirs(cls) -> None:
        for path in (cls.DATA_DIR, cls.CHROMA_DIR, cls.UPLOAD_DIR):
            path.mkdir(parents=True, exist_ok=True)
