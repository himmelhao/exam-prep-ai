"""Turns a PDF or a .txt file into plain text."""

from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path_or_file) -> str:
    """Accepts a file path or an open file object (Streamlit uploads, in Phase 2)."""
    reader = PdfReader(path_or_file)
    pages = [page.extract_text() or "" for page in reader.pages]
    return clean_text("\n\n".join(pages))


def load_text_file(path: str) -> str:
    """Load a .pdf or a plain-text file and return its text."""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return extract_pdf_text(p)
    return clean_text(p.read_text(encoding="utf-8"))


def clean_text(text: str) -> str:
    # Strip trailing spaces on each line and drop runs of blank lines.
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned, blank = [], 0
    for line in lines:
        blank = blank + 1 if not line else 0
        if blank <= 1:
            cleaned.append(line)
    return "\n".join(cleaned).strip()
