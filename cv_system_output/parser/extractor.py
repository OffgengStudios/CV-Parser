"""
parser/extractor.py — Raw text extraction from PDF and DOCX files.

Responsibility: Accept a file path, return raw text string.
All parsing logic (fields, regex) lives in parser.py — not here.
"""
import re
import zipfile
from xml.etree import ElementTree
from pathlib import Path
from typing import Optional

import pdfplumber
from docx import Document

from logger import get_logger

log = get_logger(__name__)


class ExtractionError(Exception):
    """Raised when a file cannot be read or yields no text."""
    pass


def extract_text(file_path: Path) -> str:
    """
    Dispatch to the correct extractor based on file extension.

    Args:
        file_path: Absolute or relative path to the uploaded file.

    Returns:
        Raw extracted text as a single string.

    Raises:
        ExtractionError: If the file type is unsupported, unreadable, or empty.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_path)
    elif suffix == ".docx":
        return _extract_docx(file_path)
    else:
        raise ExtractionError(f"Unsupported file type: {suffix!r}")


def _extract_pdf(file_path: Path) -> str:
    """Extract text from all pages of a PDF using pdfplumber."""
    log.info(f"Extracting PDF: {file_path.name}")
    pages_text: list[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                raise ExtractionError(f"PDF has no pages: {file_path.name}")

            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                else:
                    log.debug(f"Page {i + 1} yielded no text (image-only or blank).")

    except ExtractionError:
        raise
    except (OSError, IOError) as exc:
        log.error(f"Failed to read PDF {file_path.name} (file I/O): {exc}")
        raise ExtractionError(f"Could not read PDF: {exc}") from exc
    except Exception as exc:
        log.error(f"Unexpected error extracting PDF {file_path.name}: {exc}")
        raise ExtractionError(f"Could not read PDF: {exc}") from exc

    raw = "\n".join(pages_text).strip()
    if not raw:
        raise ExtractionError(f"No extractable text found in PDF: {file_path.name}")

    log.info(f"PDF extracted: {len(raw)} characters from {len(pages_text)} page(s).")
    return raw


def _extract_docx(file_path: Path) -> str:
    """Extract text from paragraphs, tables, and DOCX XML text containers."""
    log.info(f"Extracting DOCX: {file_path.name}")
    parts: list[str] = []

    try:
        doc = Document(str(file_path))

        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                parts.append(text)

        # Also extract text from tables (skills tables, work history grids)
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    parts.append(row_text)

        # Some CV templates store visible text in Word text boxes/shapes.
        # python-docx does not expose that text through doc.paragraphs/tables.
        if not parts:
            parts.extend(_extract_docx_xml_text(file_path))

    except (OSError, IOError) as exc:
        log.error(f"Failed to read DOCX {file_path.name} (file I/O): {exc}")
        raise ExtractionError(f"Could not read DOCX: {exc}") from exc
    except Exception as exc:
        log.error(f"Unexpected error extracting DOCX {file_path.name}: {exc}")
        raise ExtractionError(f"Could not read DOCX: {exc}") from exc

    raw = "\n".join(parts).strip()
    if not raw:
        raise ExtractionError(f"No extractable text found in DOCX: {file_path.name}")

    log.info(f"DOCX extracted: {len(raw)} characters.")
    return raw


def _extract_docx_xml_text(file_path: Path) -> list[str]:
    """Fallback extractor for text held in headers, footers, and text boxes."""
    texts: list[str] = []

    try:
        with zipfile.ZipFile(file_path) as archive:
            xml_names = [
                name
                for name in archive.namelist()
                if name.startswith("word/")
                and name.endswith(".xml")
                and (
                    name == "word/document.xml"
                    or name.startswith("word/header")
                    or name.startswith("word/footer")
                    or name.startswith("word/footnotes")
                    or name.startswith("word/endnotes")
                )
            ]

            for name in xml_names:
                root = ElementTree.fromstring(archive.read(name))
                for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                    text = (node.text or "").strip()
                    if text:
                        texts.append(text)
    except (zipfile.BadZipFile, ElementTree.ParseError) as exc:
        log.debug(f"DOCX XML fallback could not read {file_path.name}: {exc}")

    return texts


def sanitize_text(text: str) -> str:
    """
    Normalize whitespace and remove non-printable characters.
    Called after extraction, before field parsing.
    """
    # PDF extractors can emit NUL/control bytes inside otherwise valid text.
    # Remove them before parser/database layers see the content.
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"-\n(?=[a-z])", "", text)
    text = re.sub(r"[^\S\n]+", " ", text)  # Collapse spaces, preserve newlines
    text = re.sub(r"[ \t]*([|•])+[ \t]*", r" \1 ", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 blank lines
    return text.strip()
