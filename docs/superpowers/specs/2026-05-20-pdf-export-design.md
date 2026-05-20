# PDF Export — Design

**Status**: approved
**Date**: 2026-05-20

## Goal

After the multi-agent graph finishes and `final_output` is set, give the user a one-click PDF download of their paper, alongside the existing Markdown download.

## Non-goals

- Page numbers, justified body text, hanging-indent references (rejected as too complex — see brainstorming session).
- Server-side persistence of the PDF — it stays in-memory like the rest of the paper state.
- A separate "export" page or modal — the button lives where the Markdown button already lives.

## User flow

1. User completes the run (intake → researcher → drafter → reviewer → finalize).
2. The success block on `pages/1_New_Paper.py` renders two side-by-side buttons:
   - `⬇️ Download Markdown` (existing, unchanged).
   - `📄 Download PDF` (new).
3. Clicking the PDF button triggers a browser download of `paper.pdf`.

## Architecture

### New module: `agent/export_pdf.py`

```python
def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """Convert the finalized Markdown paper to PDF bytes (academic-light styling)."""
```

- Uses the `markdown-pdf` library (pure Python, no native binaries).
- Builds a `MarkdownPdf` instance, adds a single `Section(markdown_text)` with the academic-light CSS, writes to an in-memory `BytesIO`, returns the raw bytes.
- Raises on conversion failure — the caller decides how to surface it.

### Academic-light CSS (embedded in the module)

- `h1` centered, 24pt, with bottom margin.
- `h2`, `h3` left-aligned, sized hierarchy (16pt / 13pt), with top margin to separate sections.
- Body text 11pt, line-height 1.5.
- `code` (inline) uses a monospace family — this is what citation IDs like `[src-3]` render as inside section bodies.
- References section: same `h2` styling as other sections; list items get a left padding to read like an academic reference list.

### UI change: `pages/1_New_Paper.py` (lines ~228-232)

Replace the single `st.download_button` with a two-column layout:

```python
if final:
    st.success("📑 Paper complete")
    col1, col2 = st.columns(2)
    col1.download_button(
        "⬇️ Download Markdown", final,
        file_name="paper.md", mime="text/markdown",
    )
    try:
        from agent.export_pdf import markdown_to_pdf_bytes
        pdf_bytes = markdown_to_pdf_bytes(final)
        col2.download_button(
            "📄 Download PDF", pdf_bytes,
            file_name="paper.pdf", mime="application/pdf",
        )
    except Exception as e:
        col2.warning(f"PDF export unavailable: {e}")
    with st.expander("Preview", expanded=True):
        st.markdown(final)
```

PDF generation runs inline on each re-render. `markdown-pdf` is fast enough for paper-sized documents that caching is not yet warranted; if it becomes noticeable, cache in `st.session_state` keyed by `thread_id`.

### Dependency

Add `markdown-pdf>=1.3` to `requirements.txt`.

## Error handling

- The only realistic failure mode is the `markdown-pdf` library raising during conversion (e.g., a malformed snippet inside the paper).
- On failure: the Markdown button still works, and the PDF column shows a `st.warning(...)` with the exception message. The user is never left without a download path.

## Testing

One new unit test: `tests/test_export_pdf.py`.

- `test_markdown_to_pdf_bytes_returns_pdf_signature`: pass a small Markdown fixture (title, two `##` sections, a citation `[src-1]`, a References list); assert the returned `bytes` starts with `b"%PDF-"` and length > 1KB.
- No mocking of `markdown-pdf` — the test exercises the real library to catch regressions in CSS or API changes.
- No API key required, so this stays in the standard `pytest` run.

## Files touched

- `agent/export_pdf.py` — new.
- `pages/1_New_Paper.py` — modify the post-completion success block (~5 lines added).
- `requirements.txt` — one line added.
- `tests/test_export_pdf.py` — new.

## Out of scope (deferred)

- Caching the generated PDF bytes in `st.session_state`.
- Customizing per-mode styling (term papers vs. literature reviews look identical).
- Embedding figures or generated charts from the `data_analyzer` node into the PDF.
