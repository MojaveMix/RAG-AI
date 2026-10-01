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
import logging
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from config import Config

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


def _load_plain(data: bytes) -> ParsedDocument:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")

    if not text.strip():
        raise EmptyDocument("This file is empty.")
    return ParsedDocument(text=text)


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
    if ext not in Config.ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Allowed: {', '.join(sorted(Config.ALLOWED_EXTENSIONS))}"
        )

    if ext == ".pdf":
        return _load_pdf(data)
    if ext == ".docx":
        return _load_docx(data)
    return _load_plain(data)
