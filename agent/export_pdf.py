"""Convert the finalized Markdown paper to PDF bytes (academic-light styling)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from markdown_pdf import MarkdownPdf, Section


_ACADEMIC_LIGHT_CSS = """
body { font-family: "Times New Roman", Times, serif; font-size: 11pt; line-height: 1.5; }
h1 { text-align: center; font-size: 24pt; margin-bottom: 24pt; margin-top: 0; }
h2 { font-size: 16pt; margin-top: 20pt; margin-bottom: 8pt; }
h3 { font-size: 13pt; margin-top: 14pt; margin-bottom: 6pt; }
p  { text-align: left; margin: 6pt 0; }
code { font-family: "Courier New", monospace; font-size: 10pt; }
ul, ol { margin: 6pt 0 6pt 18pt; }
li { margin: 3pt 0; }
"""


def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """Render a Markdown paper to PDF bytes with academic-light styling.

    Uses a temp file because markdown-pdf.save() targets a path; we read
    the bytes back and clean up immediately.
    """
    pdf = MarkdownPdf(toc_level=2)
    pdf.add_section(Section(markdown_text, toc=False), user_css=_ACADEMIC_LIGHT_CSS)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        tmp_path = Path(fh.name)
    try:
        pdf.save(str(tmp_path))
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
