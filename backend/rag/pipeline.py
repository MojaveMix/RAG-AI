"""The RAG pipeline: ingest documents, retrieve context, answer questions."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import Any

from config import Config
from rag.chunking import build_chunks
from rag.loader import EXTENSION_TO_LANGUAGE, parse_bytes
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


_ARABIC_PATTERN = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFC]"
)

_FRENCH_INDICATORS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "en", "et", "est",
    "sont", "dans", "pour", "avec", "sur", "ce", "cet", "cette", "ces", "qui",
    "que", "quoi", "dont", "où", "quand", "comment", "pourquoi", "quel", "quelle",
    "quels", "quelles", "résume", "résumer", "explique", "donne", "parle", "document",
    "titre", "texte", "sujet", "contenu"
}

_ENGLISH_INDICATORS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "for", "of",
    "with", "to", "and", "or", "what", "where", "when", "why", "how", "which",
    "who", "whom", "whose", "summarize", "summary", "tell", "explain", "describe",
    "give", "list", "about", "this", "document", "these", "does", "did", "can"
}


def detect_language(text: str) -> str:
    """Detect whether a query is Arabic, French, or English."""
    if not text:
        return "English"
    if _ARABIC_PATTERN.search(text):
        return "Arabic"
    has_french_accents = bool(re.search(r"[éèêëàâçîïôûùœÉÈÊËÀÂÇÎÏÔÛÙ]", text))
    words = set(re.findall(r"\b\w+\b", text.lower()))
    fr_score = len(words & _FRENCH_INDICATORS) + (2 if has_french_accents else 0)
    en_score = len(words & _ENGLISH_INDICATORS)
    if fr_score > en_score:
        return "French"
    if en_score > fr_score:
        return "English"
    if has_french_accents:
        return "French"
    return "English"


def retrieve(
    question: str,
    *,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Embed the question and return the most similar chunks."""
    # An empty list or None means "search across all documents"
    filter_ids = document_ids if document_ids else None

    embedding = get_client().embed_query(question)
    return get_store().query(
        embedding,
        n_results=top_k or Config.TOP_K,
        document_ids=filter_ids,
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


def build_prompt(question: str, hits: list[dict[str, Any]], mode: str = "code") -> str:
    """Render the numbered context block injected into the user message."""
    if mode == "code":
        blocks = []
        for position, hit in enumerate(hits, start=1):
            metadata = hit.get("metadata") or {}
            location = metadata.get("filename", "source file")
            ext = metadata.get("extension", "")
            lang = EXTENSION_TO_LANGUAGE.get(ext, "")
            text = (hit.get("text") or "").strip()
            if lang:
                blocks.append(f"[{position}] File: {location} (Language: {lang})\n```{lang}\n{text}\n```")
            else:
                blocks.append(f"[{position}] File: {location}\n{text}")

        return (
            "Codebase & Document context excerpts:\n\n"
            + "\n\n".join(blocks)
            + "\n\n---\n\n"
            "CODEX & CLAUDE CODE INSTRUCTIONS:\n"
            "1. Deeply analyze the context information, data, and code above.\n"
            "2. SCHEMA & CODE GENERATION: If the user asks for SQL tables, queries, schemas, models, or code based on entities/data in the documents (such as regions, locations, tables, fields, numbers), SYNTHESIZE and GENERATE the full SQL/code solution using that data. NEVER refuse by saying the document lacks SQL queries—generate them from the extracted information!\n"
            "3. Generate COMPLETE, production-ready, clean, and robust code. Do not omit code or use lazy '// TODO: implement' comments.\n"
            "4. Format all code snippets in markdown fenced code blocks with the proper language tag (e.g. ```sql, ```python, ```typescript, ```bash, etc.).\n"
            "5. Cite referenced files using [1], [2] when explaining where data or logic originates.\n"
            "6. Provide concise technical rationale, error handling, edge cases, and run/test instructions."
        )

    # Mode: "analysis" (Document Q&A mode)
    blocks = []
    for position, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata") or {}
        location = metadata.get("filename", "document")
        if metadata.get("page"):
            location = f"{location} (page {metadata['page']})"
        text = (hit.get("text") or "").strip()
        blocks.append(f"[{position}] Source: {location}\n{text}")

    lang = detect_language(question)
    if lang == "Arabic":
        lang_rule = (
            "السؤال باللغة العربية. يجب أن تكون إجابتك بالكامل باللغة العربية فقط. "
            "لا تستخدم أي لغة أخرى حتى وإن كانت المستندات بلغة أخرى."
        )
    elif lang == "French":
        lang_rule = (
            "La question est posée en français. Vous DEVEZ obligatoirement rédiger votre réponse "
            "intégralement en français. Ne répondez pas en arabe ni en anglais, même si les extraits de documents sont en arabe ou en anglais."
        )
    else:
        lang_rule = (
            "The question is in English. You MUST write your entire response strictly in English. "
            "Do NOT reply in Arabic, French, or any other language, even if the source document excerpts are in another language."
        )

    return (
        "Context excerpts from the uploaded documents:\n\n"
        + "\n\n".join(blocks)
        + "\n\n---\n\n"
        f"Question: {question}\n\n"
        f"CRITICAL INSTRUCTIONS:\n"
        f"1. Answer using ONLY the context excerpts above, citing excerpts as [1], [2], etc.\n"
        f"2. {lang_rule}\n"
        f"3. If the context does not contain the answer, state that you could not find the information in the uploaded documents (in the same language as the question)."
    )


def build_messages(
    question: str,
    hits: list[dict[str, Any]],
    history: list[dict[str, str]] | None = None,
    mode: str = "code",
) -> list[dict[str, str]]:
    system_prompt = Config.CODE_SYSTEM_PROMPT if mode == "code" else Config.ANALYSIS_SYSTEM_PROMPT
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]

    for turn in (history or [])[-Config.MAX_HISTORY_TURNS * 2 :]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    if hits:
        messages.append({"role": "user", "content": build_prompt(question, hits, mode=mode)})
    elif mode == "code":
        # In Code mode, generate code directly like Codex / Claude Code without blocking on document uploads
        messages.append({
            "role": "user",
            "content": (
                f"{question}\n\n"
                "(Note: No codebase files or documents were uploaded or selected. "
                "Act as an autonomous coding assistant (Codex / Claude Code). Generate the full, "
                "production-ready code, complete implementation, and provide instructions to run or test it.)"
            )
        })
    else:
        lang = detect_language(question)
        if lang == "Arabic":
            no_docs_notice = (
                f"{question}\n\n"
                "(لم يتم العثور على مستندات مرفوعة أو معلومات ذات صلة. "
                "أخبر المستخدم باللغة العربية حصراً بضرورة رفع مستند أولاً.)"
            )
        elif lang == "French":
            no_docs_notice = (
                f"{question}\n\n"
                "(Aucun document pertinent n'est disponible. "
                "Indiquez à l'utilisateur en français qu'il doit d'abord importer un document.)"
            )
        else:
            no_docs_notice = (
                f"{question}\n\n"
                "(No documents are currently available or no relevant excerpts were found. "
                "Tell the user in English that they should upload a document first.)"
            )
        messages.append({"role": "user", "content": no_docs_notice})
    return messages


def answer_stream(
    question: str,
    *,
    document_ids: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
    mode: str = "code",
) -> Iterator[dict[str, Any]]:
    """Yield SSE-ready events: sources, then token deltas, then ``done``."""
    hits = retrieve(question, document_ids=document_ids)
    yield {"event": "sources", "data": format_sources(hits)}

    messages = build_messages(question, hits, history, mode=mode)
    try:
        for delta in get_client().chat_stream(messages, model=model):
            yield {"event": "delta", "data": delta}
    except Exception as exc:  # noqa: BLE001 - report mid-stream failures inline
        logger.exception("Streaming failed")
        yield {"event": "error", "data": str(exc)}
        return

    yield {"event": "done", "data": ""}
