# PDF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Download PDF" button next to the existing "Download Markdown" button on the completed-paper screen, producing a styled PDF of the finalized paper.

**Architecture:** New helper module `agent/export_pdf.py` exposes `markdown_to_pdf_bytes(text) -> bytes`, using the pure-Python `markdown-pdf` library. The Streamlit success block on `pages/1_New_Paper.py` calls it and feeds the bytes into a `st.download_button`. Academic-light CSS lives inside the helper module.

**Tech Stack:** Python, `markdown-pdf>=1.3` (pure Python, pikepdf-based), Streamlit, pytest.

**Spec:** `docs/superpowers/specs/2026-05-20-pdf-export-design.md`

---

## File Structure

- **Create** `agent/export_pdf.py` — `markdown_to_pdf_bytes(markdown_text: str) -> bytes` + academic-light CSS constant.
- **Create** `tests/test_export_pdf.py` — one unit test exercising the real library.
- **Modify** `requirements.txt` — add `markdown-pdf>=1.3`.
- **Modify** `pages/1_New_Paper.py` (lines ~225-232, the post-completion success block) — split download into two-column layout, add PDF button with try/except fallback.

---

## Task 1: Add the markdown-pdf dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency line**

Open `requirements.txt`. After the `tenacity>=9.0.0` line (just before `pytest>=8.3.0`), add:

```
markdown-pdf>=1.3
```

- [ ] **Step 2: Install it**

Run: `pip install markdown-pdf>=1.3`
Expected: successful install. `markdown-pdf` pulls in `pikepdf` and `markdown-it-py` automatically.

- [ ] **Step 3: Verify import works**

Run: `python -c "from markdown_pdf import MarkdownPdf, Section; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add markdown-pdf for PDF export"
```

---

## Task 2: Write the failing test for `markdown_to_pdf_bytes`

**Files:**
- Create: `tests/test_export_pdf.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_export_pdf.py` with:

```python
"""Unit test for the Markdown→PDF helper. No API key required."""
from agent.export_pdf import markdown_to_pdf_bytes


SAMPLE_PAPER = """# Transformer Attention Mechanisms

## Introduction

This paper reviews attention in transformers [src-1].

## Background

Self-attention was introduced by Vaswani et al. [src-2].

## References

- **[src-1]** Smith, J. (2020). Attention is great. https://example.com/a
- **[src-2]** Vaswani et al. (2017). Attention is all you need. https://arxiv.org/abs/1706.03762
"""


def test_returns_pdf_bytes():
    pdf_bytes = markdown_to_pdf_bytes(SAMPLE_PAPER)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-"), "Output must start with the PDF magic number"
    assert len(pdf_bytes) > 1024, "A real PDF for this content should be at least 1KB"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_export_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.export_pdf'` (or `ImportError`).

---

## Task 3: Implement `markdown_to_pdf_bytes` (minimal, no styling yet)

**Files:**
- Create: `agent/export_pdf.py`

- [ ] **Step 1: Write the minimal implementation**

Create `agent/export_pdf.py` with:

```python
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
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `pytest tests/test_export_pdf.py -v`
Expected: PASS. The PDF magic number check and size check both succeed.

- [ ] **Step 3: Commit**

```bash
git add agent/export_pdf.py tests/test_export_pdf.py
git commit -m "feat: add markdown_to_pdf_bytes helper for PDF export"
```

---

## Task 4: Add academic-light CSS

**Files:**
- Modify: `agent/export_pdf.py`

- [ ] **Step 1: Add the CSS constant and pass it to add_section**

Replace the entire contents of `agent/export_pdf.py` with:

```python
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
```

- [ ] **Step 2: Re-run the test to confirm styling didn't break the output**

Run: `pytest tests/test_export_pdf.py -v`
Expected: PASS. The existing assertions still hold; CSS doesn't change the magic number or make the file empty.

- [ ] **Step 3: Eyeball the output once**

Run: `python -c "from agent.export_pdf import markdown_to_pdf_bytes; open('smoke.pdf','wb').write(markdown_to_pdf_bytes('# Test\n\n## Intro\n\nHello world [src-1].\n\n## References\n\n- **[src-1]** A. Author. (2025). Sample. https://example.com'))"`
Open `smoke.pdf` and confirm: title centered, headings hierarchy visible, body text serif, `[src-1]` in monospace. Then `del smoke.pdf` (Windows) — do NOT commit it.

- [ ] **Step 4: Commit**

```bash
git add agent/export_pdf.py
git commit -m "feat: add academic-light CSS to PDF export"
```

---

## Task 5: Wire the PDF button into the Streamlit UI

**Files:**
- Modify: `pages/1_New_Paper.py:222-232`

- [ ] **Step 1: Locate the current success block**

Open `pages/1_New_Paper.py`. The block currently looks like:

```python
elif st.session_state.run_started:
    # Run completed
    graph = get_graph()
    snapshot = graph.get_state(config())
    final = snapshot.values.get("final_output")
    if final:
        st.success("📑 Paper complete")
        st.download_button("⬇️ Download Markdown", final,
                           file_name="paper.md", mime="text/markdown")
        with st.expander("Preview", expanded=True):
            st.markdown(final)
```

- [ ] **Step 2: Replace it with the two-button version**

Use Edit to replace the block above with:

```python
elif st.session_state.run_started:
    # Run completed
    graph = get_graph()
    snapshot = graph.get_state(config())
    final = snapshot.values.get("final_output")
    if final:
        st.success("📑 Paper complete")
        col_md, col_pdf = st.columns(2)
        col_md.download_button(
            "⬇️ Download Markdown", final,
            file_name="paper.md", mime="text/markdown",
            use_container_width=True,
        )
        try:
            from agent.export_pdf import markdown_to_pdf_bytes
            pdf_bytes = markdown_to_pdf_bytes(final)
            col_pdf.download_button(
                "📄 Download PDF", pdf_bytes,
                file_name="paper.pdf", mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            col_pdf.warning(f"PDF export unavailable: {e}")
        with st.expander("Preview", expanded=True):
            st.markdown(final)
```

- [ ] **Step 3: Run the unit tests to confirm nothing else regressed**

Run: `pytest -q`
Expected: all existing tests pass + the new `test_returns_pdf_bytes` passes.

- [ ] **Step 4: Commit**

```bash
git add pages/1_New_Paper.py
git commit -m "feat(ui): add Download PDF button on completed paper screen"
```

---

## Task 6: Manual smoke test in Streamlit

**Files:** none — verification only.

- [ ] **Step 1: Start the app**

Run: `streamlit run app.py`
Expected: dashboard loads at `http://localhost:8501`.

- [ ] **Step 2: Drive a short paper through completion**

Pick **Term Paper** (fastest — no review loop). Give a small topic like "Photosynthesis basics". Approve outline → approve sources → approve draft. The success block should appear.

- [ ] **Step 3: Verify both buttons**

- Click **Download Markdown** — `paper.md` downloads. Open it, confirm the content.
- Click **Download PDF** — `paper.pdf` downloads. Open it, confirm:
  - Centered title at the top.
  - Section headings visible and hierarchical.
  - Body text in serif.
  - Citation IDs (`[src-1]`, `[src-2]`, …) appear in monospace.
  - References section at the bottom.

- [ ] **Step 4: Verify the failure fallback (optional)**

Manually break the `markdown_to_pdf_bytes` import (e.g. rename the function temporarily) and re-render — the PDF column should show the `st.warning(...)` while the Markdown button still works. Revert the change. **Do not commit this revert if you didn't commit the break.**

- [ ] **Step 5: Stop the server**

`Ctrl+C` in the terminal running Streamlit.

---

## Self-review checklist (already applied)

- Spec coverage: every section of `2026-05-20-pdf-export-design.md` maps to a task (deps → Task 1, helper module → Tasks 2–4, UI wiring → Task 5, manual verification → Task 6, test → Task 2).
- No placeholders: every step contains the exact code or command.
- Type consistency: the function name `markdown_to_pdf_bytes` is identical across the test, the helper, and the UI call site.
