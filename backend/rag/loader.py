"""Text extraction for the supported upload formats.

PDF loading strategy (in order):
1. PyMuPDF        – best text extraction for digital/native PDFs.
2. pypdf          – fallback if PyMuPDF is not installed.
3. OCR via PyMuPDF page rendering + Tesseract – for truly scanned/image-only PDFs.
   PyMuPDF renders each page to a pixel image internally (no Poppler needed).
   Tesseract does the OCR. Auto-detected on Windows even when not on PATH.
"""

from __future__ import annotations

import io
import json
import logging
import os
import platform
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from config import Config
from rag.chunking import clean_text

logger = logging.getLogger(__name__)


class UnsupportedFileType(ValueError):
    """Raised when a file extension is not in ``Config.ALLOWED_EXTENSIONS``."""


class EmptyDocument(ValueError):
    """Raised when a file contains no extractable text (e.g. a scanned PDF)."""


@dataclass
class ParsedDocument:
    text: str
    pages: int | None = None
    page_texts: list[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_pymupdf():
    """Import PyMuPDF under either package name; return module or None."""
    try:
        import pymupdf  # type: ignore[import]
        return pymupdf
    except ImportError:
        pass
    try:
        import fitz  # type: ignore[import]
        return fitz
    except ImportError:
        return None


def _find_tesseract() -> str | None:
    """Return the path to the Tesseract binary, or None if not found."""
    if shutil.which("tesseract"):
        return shutil.which("tesseract")
    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
            os.path.join(os.environ.get("APPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
    return None


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def _extract_text_pymupdf(data: bytes) -> tuple[list[str], int] | None:
    """Extract text layer using PyMuPDF. Returns None if not installed."""
    fitz = _import_pymupdf()
    if fitz is None:
        return None
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise EmptyDocument(f"Could not open PDF: {exc}") from exc
    pages = [page.get_text("text") or "" for page in doc]
    return pages, len(doc)


def _extract_text_pypdf(data: bytes) -> tuple[list[str], int]:
    """Extract text layer using pypdf (always available as a fallback)."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    try:
        reader = PdfReader(io.BytesIO(data))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                pass
        pages = [page.extract_text() or "" for page in reader.pages]
        return pages, len(reader.pages)
    except PdfReadError as exc:
        raise EmptyDocument(f"Could not read the PDF: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise EmptyDocument(f"Could not read the PDF: {exc}") from exc


def _ocr_with_pymupdf_and_tesseract(data: bytes) -> tuple[list[str], int]:
    """
    Render each PDF page to an image using PyMuPDF (no Poppler needed),
    then run Tesseract OCR on each image.

    Requires:
      - pymupdf Python package   (pip install pymupdf)   ← already installed
      - pytesseract Python package (pip install pytesseract)  ← already installed
      - Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki
    """
    fitz = _import_pymupdf()
    if fitz is None:
        raise EmptyDocument(
            "This PDF is image-only (scanned). PyMuPDF is needed to render pages.\n"
            "Fix: pip install pymupdf"
        )

    try:
        import pytesseract  # type: ignore[import]
        from PIL import Image  # type: ignore[import]
    except ImportError:
        raise EmptyDocument(
            "This PDF is image-only (scanned). pytesseract is needed for OCR.\n"
            "Fix: pip install pytesseract"
        )

    # Point pytesseract at the binary — auto-detect on Windows
    tess_path = _find_tesseract()
    if tess_path is None:
        raise EmptyDocument(
            "Tesseract OCR is not installed.\n"
            "Download and install it from:\n"
            "  https://github.com/UB-Mannheim/tesseract/wiki\n"
            "Then restart the backend server."
        )
    pytesseract.pytesseract.tesseract_cmd = tess_path
    logger.info("OCR: using Tesseract at %s", tess_path)

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise EmptyDocument(f"Could not open PDF for OCR rendering: {exc}") from exc

    page_texts: list[str] = []
    for page_num, page in enumerate(doc):
        # Render at 200 DPI — good balance between speed and OCR accuracy
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        try:
            text = pytesseract.image_to_string(img, lang="eng+fra+ara")
        except pytesseract.TesseractNotFoundError:
            raise EmptyDocument(
                f"Tesseract binary not found at '{tess_path}'.\n"
                "Reinstall it from: https://github.com/UB-Mannheim/tesseract/wiki"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("OCR failed on page %d: %s", page_num + 1, exc)
            text = ""
        page_texts.append(text)
        logger.debug("OCR page %d/%d done (%d chars)", page_num + 1, len(doc), len(text))

    return page_texts, len(doc)


def _load_pdf(data: bytes) -> ParsedDocument:
    """
    Extract text from a PDF with a 3-step fallback:
      1. PyMuPDF text layer  (fast, handles 95% of PDFs)
      2. pypdf text layer    (fallback if PyMuPDF missing)
      3. Tesseract OCR       (for truly scanned/image-only PDFs)
    """
    # Step 1 & 2 — try text extraction
    result = _extract_text_pymupdf(data)
    if result is None:
        logger.debug("PyMuPDF not available, falling back to pypdf")
        result = _extract_text_pypdf(data)

    pages, total = result
    text = "\n\n".join(p.strip() for p in pages if p.strip())

    # Step 3 — no text layer found → OCR
    if not text.strip():
        logger.info("No text layer in PDF — running OCR on %d pages…", total)
        pages, total = _ocr_with_pymupdf_and_tesseract(data)
        text = "\n\n".join(p.strip() for p in pages if p.strip())

    if not text.strip():
        raise EmptyDocument(
            "No text could be extracted from this PDF even after OCR. "
            "The scan quality may be too low, or the document may be blank."
        )

    return ParsedDocument(
        text=text,
        pages=total,
        page_texts=[p.strip() for p in pages],
    )


# ---------------------------------------------------------------------------
# Other formats
# ---------------------------------------------------------------------------

def _load_docx(data: bytes) -> ParsedDocument:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise EmptyDocument(f"Could not read the DOCX file: {exc}") from exc

    blocks: list[str] = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                blocks.append(" | ".join(cells))

    text = "\n".join(blocks)
    if not text.strip():
        raise EmptyDocument("No text found in this DOCX file.")
    return ParsedDocument(text=text)


def _decode_plain(data: bytes) -> str:
    """Decode a text file in any language without guessing the wrong legacy codepage.

    Legacy single-byte codepages (cp1252 for French, cp1256 for Arabic...) accept
    almost any byte sequence, so they cannot simply be tried in a fixed order:

    1. BOM / UTF-16 and strict UTF-8 cover every modern file.
    2. Latin-script languages (French, Spanish, German...) only use a few accented
       letters, so a low share of non-ASCII bytes means cp1252.
    3. A file that is mostly non-ASCII is a non-Latin script (Arabic, Cyrillic,
       Greek, CJK...), where statistical detection is reliable.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass

    non_ascii_ratio = sum(byte >= 0x80 for byte in data) / max(len(data), 1)
    if non_ascii_ratio >= 0.2:
        try:
            from charset_normalizer import from_bytes

            best = from_bytes(data).best()
            if best is not None:
                return str(best)
        except Exception:  # noqa: BLE001 - detection is best-effort
            logger.debug("charset detection failed", exc_info=True)

    try:
        return data.decode("cp1252")
    except UnicodeDecodeError:
        return data.decode("latin-1")


EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".ipynb": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".d.ts": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".jsonc": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".csv": "csv",
    ".tsv": "tsv",
    ".sql": "sql",
    ".cql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".ps1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hh": "cpp",
    ".cs": "csharp",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".r": "r",
    ".dart": "dart",
    ".lua": "lua",
    ".vue": "vue",
    ".svelte": "svelte",
    ".astro": "astro",
    ".dockerfile": "dockerfile",
    ".containerfile": "dockerfile",
    ".env": "properties",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".properties": "properties",
    ".gradle": "groovy",
    ".cmake": "cmake",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".prisma": "prisma",
}


def _load_plain(data: bytes) -> ParsedDocument:
    text = _decode_plain(data)

    if not text.strip():
        raise EmptyDocument("This file is empty.")
    return ParsedDocument(text=text)


def _load_ipynb(data: bytes) -> ParsedDocument:
    """Parse Jupyter Notebook JSON into structured code and markdown blocks."""
    raw = _decode_plain(data)
    try:
        nb = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise EmptyDocument(f"Could not parse Jupyter Notebook JSON: {exc}") from exc

    cells = nb.get("cells") or []
    sections: list[str] = []

    for idx, cell in enumerate(cells, start=1):
        cell_type = cell.get("cell_type", "code")
        source = "".join(cell.get("source") or []).strip()
        if not source:
            continue
        if cell_type == "markdown":
            sections.append(f"### [Cell {idx} - Markdown]\n{source}")
        else:
            sections.append(f"### [Cell {idx} - Code (Python)]\n```python\n{source}\n```")

    if not sections:
        raise EmptyDocument("This notebook contains no code or markdown cells.")

    return ParsedDocument(text="\n\n".join(sections))


def _load_zip(data: bytes) -> ParsedDocument:
    """Extract code and text files from a ZIP archive and combine them into a codebase manifest."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise EmptyDocument(f"Could not read ZIP archive: {exc}") from exc

    ignored_dirs = (
        "__pycache__", "node_modules", ".git/", ".venv/", ".idea/",
        ".vscode/", "dist/", "build/", ".next/", "vendor/", "target/"
    )
    binary_exts = {
        ".exe", ".dll", ".so", ".bin", ".iso", ".png", ".jpg", ".jpeg",
        ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".pyc", ".class",
        ".jar", ".war", ".ear", ".wasm", ".7z", ".rar"
    }

    file_sections: list[str] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        rel_path = info.filename
        if any(ign in rel_path for ign in ignored_dirs):
            continue
        ext = Path(rel_path).suffix.lower()
        if ext in binary_exts:
            continue

        try:
            raw_file = zf.read(info)
            if not raw_file or (b"\x00" in raw_file[:4096] and not raw_file.startswith((b"\xff\xfe", b"\xfe\xff"))):
                continue
            content = _decode_plain(raw_file).strip()
            if not content:
                continue
            lang = EXTENSION_TO_LANGUAGE.get(ext, "")
            header = f"================================================================================\nFile: {rel_path}"
            if lang:
                file_sections.append(f"{header}\nLanguage: {lang}\n================================================================================\n```{lang}\n{content}\n```")
            else:
                file_sections.append(f"{header}\n================================================================================\n{content}")
        except Exception:  # noqa: BLE001
            continue

    if not file_sections:
        raise EmptyDocument("No readable text or code files found in this ZIP archive.")

    return ParsedDocument(text="\n\n".join(file_sections))


def _is_binary(data: bytes) -> bool:
    """Check whether data appears to be binary by inspecting for null bytes."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    sample = data[:4096]
    return b"\x00" in sample


def _load_code_or_text(data: bytes, filename: str) -> ParsedDocument:
    """Load any code or text file, formatted with code language tagging."""
    if _is_binary(data):
        raise UnsupportedFileType(
            f"'{filename}' appears to be a binary file. RAG AI processes code, scripts, text and documents."
        )
    return _load_plain(data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(path: Path, extension: str | None = None) -> ParsedDocument:
    """Extract text from ``path`` based on its extension."""
    return parse_bytes(path.read_bytes(), f"upload{extension or path.suffix}")


def parse_bytes(data: bytes, filename: str) -> ParsedDocument:
    """Extract text from an in-memory upload, keyed off ``filename``."""
    if not data:
        raise EmptyDocument("This file is empty (0 bytes).")

    ext = Path(filename).suffix.lower()
    base_name = Path(filename).name.lower()

    # Determine if supported: known extension, recognized developer filename, or general plain text
    is_known_ext = ext in Config.ALLOWED_EXTENSIONS
    is_known_file = base_name in getattr(Config, "ALLOWED_FILENAMES", set())
    
    if not is_known_ext and not is_known_file:
        if _is_binary(data):
            raise UnsupportedFileType(
                f"Unsupported file type '{ext or filename}'. "
                f"Please upload code, text, documents or zip archives."
            )

    if ext == ".pdf":
        doc = _load_pdf(data)
    elif ext == ".docx":
        doc = _load_docx(data)
    elif ext == ".ipynb":
        doc = _load_ipynb(data)
    elif ext == ".zip":
        doc = _load_zip(data)
    else:
        doc = _load_code_or_text(data, filename)

    # Language-neutral cleanup: NFC accents, ligatures, zero-width marks, tatweel
    doc.text = clean_text(doc.text)
    if doc.page_texts:
        doc.page_texts = [clean_text(pt) for pt in doc.page_texts]
    return doc
