"""Recursive character text splitter with multilingual and Arabic support.

Mirrors the behaviour of LangChain's ``RecursiveCharacterTextSplitter`` without
pulling in the dependency: try to keep the largest natural separator that fits
inside the chunk budget, and recurse into smaller separators for the remainder.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

# Separators ordered from largest logical block to smallest character split.
# Supports Latin/English/French (. ! ? ; ,) and Arabic (؟ ؛ ،).
DEFAULT_SEPARATORS = [
    "\n\n",
    "\n",
    ". ",
    "؟ ",
    "? ",
    "! ",
    "؛ ",
    "; ",
    "، ",
    ", ",
    " ",
    "",
]

# Latin ligatures (ﬁ, ﬂ...) and Arabic presentation forms are mapped to plain letters.
_COMPAT_FORMS = re.compile("[\ufb00-\ufb06\ufb50-\ufdff\ufe70-\ufefc]+")
# Invisible characters that carry no meaning.
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\ufeff\u200e\u200f\u00ad\u0640"), None)


def clean_text(text: str) -> str:
    """Language-neutral text cleanup applied before chunking and embedding.

    - NFC normalisation (fixes decomposed accents in French PDFs).
    - Ligatures / Arabic presentation forms folded to plain letters via NFKC.
    - Removes zero-width marks, soft hyphens and Arabic tatweel (kashida).
    """
    if not text:
        return ""
    text = _COMPAT_FORMS.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), text)
    text = unicodedata.normalize("NFC", text)
    return text.translate(_INVISIBLE)


clean_arabic_text = clean_text


@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)


def _split_with_separator(text: str, separators: list[str]) -> list[str]:
    """Split ``text`` on the first separator that actually occurs."""
    for separator in separators:
        if separator == "":
            return [text]
        if separator in text:
            return text.split(separator)
    return [text]


def _join_pieces(pieces: list[str], separator: str) -> str:
    return separator.join(piece for piece in pieces if piece != "")


def split_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list[str] | None = None,
) -> list[str]:
    """Split ``text`` into overlapping chunks of at most ``chunk_size`` chars."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    separators = separators or DEFAULT_SEPARATORS
    text = clean_text(text).strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    def flush() -> None:
        nonlocal current, current_length
        joined = _join_pieces(current, separators[-1] if len(current) > 1 else "")
        if joined.strip():
            chunks.append(joined.strip())
        # Rebuild the tail of the window so consecutive chunks overlap.
        if chunk_overlap > 0 and chunks:
            tail: list[str] = []
            tail_length = 0
            for piece in reversed(chunks[-1].split(separators[0] if separators[0] else "")):
                if tail_length + len(piece) > chunk_overlap:
                    break
                tail.insert(0, piece)
                tail_length += len(piece) + len(separators[0])
            current = tail
            current_length = tail_length
        else:
            current = []
            current_length = 0

    def process(remaining: str, active_separators: list[str]) -> None:
        nonlocal current, current_length
        pieces = _split_with_separator(remaining, active_separators)
        if pieces == [remaining] and len(active_separators) > 1:
            # Separator not present: descend into the next one.
            process(remaining, active_separators[1:])
            return

        join_with = active_separators[0] if active_separators[0] else ""
        for piece in pieces:
            if len(piece) > chunk_size:
                # Flush what we have, then hard-split this oversized piece.
                if current:
                    flush()
                for start in range(0, len(piece), chunk_size - chunk_overlap):
                    window = piece[start : start + chunk_size]
                    if window.strip():
                        chunks.append(window.strip())
                continue

            if current_length + len(piece) + len(join_with) > chunk_size:
                flush()
            current.append(piece)
            current_length += len(piece) + len(join_with)

    process(text, list(separators))

    if current:
        joined = _join_pieces(current, separators[-1] if len(current) > 1 else "")
        if joined.strip():
            chunks.append(joined.strip())

    # De-duplicate identical adjacent chunks produced by the overlap window.
    deduped: list[str] = []
    for chunk in chunks:
        if not deduped or deduped[-1] != chunk:
            deduped.append(chunk)
    return deduped


def build_chunks(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
    base_metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Split ``text`` and attach ``base_metadata`` plus a 1-based chunk index."""
    base = dict(base_metadata or {})
    pieces = split_text(text, chunk_size, chunk_overlap)
    return [
        Chunk(text=piece, index=position + 1, metadata={**base, "chunk_index": position + 1})
        for position, piece in enumerate(pieces)
        if piece.strip()
    ]
