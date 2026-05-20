"""Convert the finalized Markdown paper to PDF bytes (academic-light styling)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from markdown_pdf import MarkdownPdf, Section


def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """Render a Markdown paper to PDF bytes.

    Uses a temp file because markdown-pdf.save() targets a path; we read
    the bytes back and clean up immediately.
    """
    pdf = MarkdownPdf(toc_level=2)
    pdf.add_section(Section(markdown_text, toc=False))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        tmp_path = Path(fh.name)
    try:
        pdf.save(str(tmp_path))
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
