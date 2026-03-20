"""
resume_extractor/extractor.py
------------------------------
Extracts clean, structured text from a resume file.

Supported formats:
  - PDF  (.pdf)  — via pdfplumber (layout-aware, handles columns)
  - Word (.docx) — via python-docx (preserves heading hierarchy)
  - Text (.txt)  — via chardet (auto-detects encoding)

Usage:
    from extractor import extract_resume_text, ResumeExtractionError

    result = extract_resume_text("resume.pdf")
    print(result["text"])        # clean full text
    print(result["sections"])    # {"experience": "...", "skills": "...", ...}
    print(result["metadata"])    # {"pages": 2, "format": "pdf", "word_count": 412}
"""

import os
import re
import pathlib
import logging
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
import chardet
from docx import Document
from docx.oxml.ns import qn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ResumeExtractionError(Exception):
    """Raised when extraction fails for a known, handleable reason."""
    pass

class UnsupportedFormatError(ResumeExtractionError):
    """Raised when the file format is not supported."""
    pass

class EmptyDocumentError(ResumeExtractionError):
    """Raised when the extracted text is empty or unusably short."""
    pass


# ---------------------------------------------------------------------------
# Section header patterns  (order matters — first match wins)
# ---------------------------------------------------------------------------

SECTION_PATTERNS = [
    ("contact",     r"(contact|personal\s+info|personal\s+details)"),
    ("summary",     r"(summary|objective|profile|about\s+me|professional\s+summary)"),
    ("experience",  r"(experience|work\s+history|employment|work\s+experience|professional\s+experience)"),
    ("education",   r"(education|academic|qualification|degree|university|college)"),
    ("skills",      r"(skills|technical\s+skills|core\s+competencies|competencies|technologies|tools)"),
    ("projects",    r"(projects|personal\s+projects|notable\s+projects|portfolio)"),
    ("certifications", r"(certif|license|accreditation|credential)"),
    ("languages",   r"(languages|language\s+proficiency)"),
    ("awards",      r"(awards|honors|achievements|accomplishments)"),
    ("publications",r"(publications|papers|research)"),
]

# Lines that are almost certainly section headers
HEADER_RE = re.compile(
    r"^\s*(" + "|".join(p for _, p in SECTION_PATTERNS) + r")\s*[:\-–—]?\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Text cleaning helpers
# ---------------------------------------------------------------------------

def _clean_text(raw: str) -> str:
    """
    Normalize whitespace, remove junk characters, and standardize line endings.
    Preserves meaningful blank lines between sections.
    """
    # Normalize unicode dashes and quotes
    raw = raw.replace("\u2013", "-").replace("\u2014", "-")
    raw = raw.replace("\u2018", "'").replace("\u2019", "'")
    raw = raw.replace("\u201c", '"').replace("\u201d", '"')
    raw = raw.replace("\u2022", "-").replace("\u2023", "-")  # bullets → dash
    raw = raw.replace("\u00b7", "-")                          # middle dot → dash
    raw = raw.replace("\xa0", " ")                            # non-breaking space

    # Remove null bytes and other control chars except newlines and tabs
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)

    # Normalize tabs to spaces
    raw = raw.replace("\t", "  ")

    # Strip trailing whitespace on each line
    lines = [line.rstrip() for line in raw.splitlines()]

    # Collapse runs of 3+ blank lines to 2
    cleaned_lines = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned_lines.append("")
        else:
            blank_count = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _remove_headers_footers(lines: list[str]) -> list[str]:
    """
    Heuristic: remove lines that look like page headers/footers.
    These are typically very short lines containing only a page number
    or repeated candidate name appearing at top/bottom of each page.
    """
    # Detect lines that are just page numbers: "1", "Page 1", "- 2 -"
    page_num_re = re.compile(r"^\s*[-–—]?\s*(page\s+)?\d+\s*[-–—]?\s*$", re.IGNORECASE)

    return [line for line in lines if not page_num_re.match(line)]


# ---------------------------------------------------------------------------
# Section splitter
# ---------------------------------------------------------------------------

def _split_into_sections(text: str) -> dict[str, str]:
    """
    Splits clean resume text into named sections.
    Returns a dict: {section_name: section_text}.
    Unclassified text before the first header goes under 'header' (name/contact).
    """
    sections: dict[str, list[str]] = {"header": []}
    current_section = "header"

    for line in text.splitlines():
        stripped = line.strip()

        # Check if this line is a section heading
        matched_section = None
        if stripped and len(stripped) < 60:  # headers are short
            for section_name, pattern in SECTION_PATTERNS:
                if re.match(r"^\s*" + pattern + r"\s*[:\-–—]?\s*$", stripped, re.IGNORECASE):
                    matched_section = section_name
                    break

        if matched_section:
            current_section = matched_section
            if current_section not in sections:
                sections[current_section] = []
        else:
            sections[current_section].append(line)

    # Join each section's lines, strip extra whitespace
    return {
        k: "\n".join(v).strip()
        for k, v in sections.items()
        if "\n".join(v).strip()  # drop empty sections
    }


# ---------------------------------------------------------------------------
# Format-specific extractors
# ---------------------------------------------------------------------------

def _extract_from_pdf(filepath: str) -> str:
    """
    Extract text from PDF using pdfplumber.
    Strategy:
      - Try layout-aware extraction first (handles columns)
      - Fall back to simple extraction if layout gives garbage
    """
    all_pages: list[str] = []

    with pdfplumber.open(filepath) as pdf:
        if len(pdf.pages) == 0:
            raise EmptyDocumentError("PDF has no pages.")

        for page_num, page in enumerate(pdf.pages, start=1):
            # Layout-aware: extract words sorted by position
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=True,   # respects reading order
            )

            if words:
                # Reconstruct lines from word positions
                page_text = _words_to_lines(words, page.width)
            else:
                # Fallback: simple text extraction
                page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

            if page_text.strip():
                all_pages.append(page_text)

    if not all_pages:
        raise EmptyDocumentError("Could not extract any text from PDF. It may be a scanned image.")

    return "\n\n".join(all_pages)


def _words_to_lines(words: list[dict], page_width: float) -> str:
    """
    Convert pdfplumber word objects back into lines of text,
    detecting multi-column layouts by clustering x-positions.
    """
    if not words:
        return ""

    # Sort words by vertical position (top), then horizontal (x0)
    words_sorted = sorted(words, key=lambda w: (round(w["top"] / 5) * 5, w["x0"]))

    # Group into lines by y-proximity (within 5 pts = same line)
    lines: list[list[dict]] = []
    current_line: list[dict] = [words_sorted[0]]

    for word in words_sorted[1:]:
        prev = current_line[-1]
        # Same line if tops are within 5 points
        if abs(word["top"] - prev["top"]) < 5:
            current_line.append(word)
        else:
            lines.append(sorted(current_line, key=lambda w: w["x0"]))
            current_line = [word]
    lines.append(sorted(current_line, key=lambda w: w["x0"]))

    # Reconstruct text: add space between words, detect column break
    result_lines = []
    for line_words in lines:
        text = ""
        for i, word in enumerate(line_words):
            if i == 0:
                text += word["text"]
            else:
                gap = word["x0"] - line_words[i - 1]["x1"]
                # Large gap (> 30pt) suggests a column separator — add a separator
                if gap > 30:
                    text += "  |  " + word["text"]
                else:
                    text += " " + word["text"]
        result_lines.append(text)

    return "\n".join(result_lines)


def _extract_from_docx(filepath: str) -> str:
    """
    Extract text from .docx preserving paragraph order and heading hierarchy.
    Also extracts text from tables (common in resume templates).
    """
    doc = Document(filepath)
    lines: list[str] = []

    for element in doc.element.body:
        tag = element.tag.split("}")[-1]  # strip namespace

        if tag == "p":
            # It's a paragraph
            para_text = "".join(node.text or "" for node in element.iter() if node.tag.endswith("}t"))
            if para_text.strip():
                lines.append(para_text.strip())

        elif tag == "tbl":
            # It's a table — flatten each row
            for row in element.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                row_cells = []
                for cell in row.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"):
                    cell_text = "".join(
                        node.text or ""
                        for node in cell.iter()
                        if node.tag.endswith("}t")
                    ).strip()
                    if cell_text:
                        row_cells.append(cell_text)
                if row_cells:
                    lines.append("  |  ".join(row_cells))

    if not lines:
        raise EmptyDocumentError("No text found in the Word document.")

    return "\n".join(lines)


def _extract_from_txt(filepath: str) -> str:
    """
    Read a plain text file, auto-detecting encoding using chardet.
    """
    with open(filepath, "rb") as f:
        raw_bytes = f.read()

    if not raw_bytes.strip():
        raise EmptyDocumentError("Text file is empty.")

    detection = chardet.detect(raw_bytes)
    encoding = detection.get("encoding") or "utf-8"
    confidence = detection.get("confidence", 0)

    logger.info(f"Detected encoding: {encoding} (confidence: {confidence:.0%})")

    try:
        return raw_bytes.decode(encoding, errors="replace")
    except (UnicodeDecodeError, LookupError):
        # Last resort
        return raw_bytes.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _detect_format(filepath: str) -> str:
    """
    Detect file format from extension, with a basic magic-byte fallback.
    Returns: 'pdf', 'docx', or 'txt'
    """
    ext = pathlib.Path(filepath).suffix.lower()

    if ext == ".pdf":
        return "pdf"
    elif ext in (".docx", ".doc"):
        return "docx"
    elif ext in (".txt", ".text", ".md", ".rtf"):
        return "txt"
    else:
        # Try magic bytes
        with open(filepath, "rb") as f:
            header = f.read(8)
        if header[:4] == b"%PDF":
            return "pdf"
        elif header[:4] == b"PK\x03\x04":  # ZIP-based = docx
            return "docx"
        else:
            # Attempt to decode as text
            return "txt"


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def extract_resume_text(filepath: str) -> dict:
    """
    Extract and clean text from a resume file.

    Args:
        filepath: Path to the resume file (.pdf, .docx, .txt)

    Returns:
        {
            "text":     str   — full cleaned text,
            "sections": dict  — {"skills": "...", "experience": "...", ...},
            "metadata": dict  — {"pages": int, "format": str, "word_count": int,
                                  "char_count": int, "encoding": str}
        }

    Raises:
        FileNotFoundError:      if file does not exist
        UnsupportedFormatError: if file format cannot be handled
        EmptyDocumentError:     if no usable text could be extracted
        ResumeExtractionError:  for other extraction failures
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        raise EmptyDocumentError("File is empty (0 bytes).")
    if file_size > 10 * 1024 * 1024:  # 10 MB guard
        raise ResumeExtractionError("File exceeds 10MB limit. Please provide a smaller file.")

    fmt = _detect_format(filepath)
    logger.info(f"Detected format: {fmt} for file: {filepath}")

    # --- Extract raw text ---
    try:
        if fmt == "pdf":
            raw_text = _extract_from_pdf(filepath)
            pages = _count_pdf_pages(filepath)
        elif fmt == "docx":
            raw_text = _extract_from_docx(filepath)
            pages = 1  # docx doesn't have a meaningful page count without rendering
        elif fmt == "txt":
            raw_text = _extract_from_txt(filepath)
            pages = 1
        else:
            raise UnsupportedFormatError(
                f"Format '{fmt}' is not supported. Please upload a PDF, DOCX, or TXT file."
            )
    except (EmptyDocumentError, UnsupportedFormatError):
        raise
    except Exception as e:
        raise ResumeExtractionError(f"Extraction failed for {fmt.upper()}: {str(e)}") from e

    # --- Clean ---
    lines = raw_text.splitlines()
    lines = _remove_headers_footers(lines)
    cleaned = _clean_text("\n".join(lines))

    if len(cleaned.split()) < 20:
        raise EmptyDocumentError(
            "Extracted text is too short to be a valid resume "
            f"(only {len(cleaned.split())} words found). "
            "If this is a scanned PDF, OCR support is required."
        )

    # --- Split into sections ---
    sections = _split_into_sections(cleaned)

    # --- Build metadata ---
    metadata = {
        "format":     fmt,
        "pages":      pages,
        "word_count": len(cleaned.split()),
        "char_count": len(cleaned),
        "sections_found": list(sections.keys()),
    }

    logger.info(
        f"Extraction complete: {metadata['word_count']} words, "
        f"{len(sections)} sections: {list(sections.keys())}"
    )

    return {
        "text":     cleaned,
        "sections": sections,
        "metadata": metadata,
    }


def _count_pdf_pages(filepath: str) -> int:
    with pdfplumber.open(filepath) as pdf:
        return len(pdf.pages)


# ---------------------------------------------------------------------------
# CLI utility — run directly to test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <resume_file>")
        sys.exit(1)

    try:
        result = extract_resume_text(sys.argv[1])
        print("\n" + "="*60)
        print("METADATA")
        print("="*60)
        print(json.dumps(result["metadata"], indent=2))

        print("\n" + "="*60)
        print("SECTIONS FOUND")
        print("="*60)
        for section, content in result["sections"].items():
            print(f"\n[{section.upper()}]")
            print(content[:300] + ("..." if len(content) > 300 else ""))

        print("\n" + "="*60)
        print("FULL CLEAN TEXT (first 800 chars)")
        print("="*60)
        print(result["text"][:800])

    except ResumeExtractionError as e:
        print(f"Extraction error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        sys.exit(1)
