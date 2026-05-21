# 📑 Research Paper Agent

Multi-agent academic writing assistant — a LangGraph state machine of three specialists
(Researcher → Drafter → Reviewer) that produces grounded, cited research papers in three
modes, with three human-in-the-loop checkpoints and Supabase-backed persistence.

## Modes

- **survey** — literature review / synthesis paper (full review loop)
- **empirical** — built around your uploaded data (CSV/PDF/TXT), adds a data-analyzer step
- **term** — standard university essay (single drafter pass, no review loop)

At each of three checkpoints — **outline → sources → draft** — the human approves or
edits before the graph continues. Threads and uploaded files persist in Supabase, so
papers can be resumed across sessions or after a server restart.

## Document grounding

When the user uploads reading material:

- The **Researcher** is told docs are present and instructed to call `document_search`
  at least once per outline section, surfacing passages as `Source` entries.
- The **Drafter** runs its own per-section FAISS similarity search and gets the
  retrieved chunks injected into its prompt as a `REFERENCE PASSAGES` block, with
  inline citations in `(filename, page N)` form.

Empirical mode keeps its dedicated `data_analyzer` path on top of this.

## Stack

- **LLM**: OpenAI (`gpt-4o-mini` by default; allowlist enforced in `validators.py`)
- **Orchestration**: LangGraph `StateGraph` with `interrupt_before` checkpoints
- **Persistence**: Supabase — Postgres-backed `PostgresSaver` for LangGraph checkpoints,
  `papers` / `paper_files` tables for app metadata, and Storage for uploaded blobs
- **Retrieval**: FAISS + `bge-small-en` embeddings via FastEmbed
- **Tools**: DuckDuckGo, Wikipedia, arXiv, Python REPL, document search
- **UI**: Streamlit multipage (dashboard + New Paper page) with checkpoint-card flow
- **Export**: Markdown + PDF (via `markdown-pdf`)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in:

- `OPENAI_API_KEY` — your OpenAI key
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL` — from your Supabase project
  (Settings → API for the first two, Settings → Database → Connection string for the URL)

Apply the schema once per Supabase project:

```bash
# In the Supabase SQL editor, paste and run the contents of:
docs/supabase_setup.sql
```

This creates the `papers` and `paper_files` tables, the `paper-files` storage bucket,
and the LangGraph checkpointer tables.

## Run

```bash
streamlit run app.py
```

The dashboard (`app.py`) lets you pick a mode or resume a previous paper. The
`New Paper` page (`pages/1_New_Paper.py`) runs the multi-agent flow and walks you
through the three checkpoints.

## Test

Unit tests (no API key needed):

```bash
pytest
```

End-to-end integration (real OpenAI calls, takes ~2–5 min):

```bash
python verify_pipeline.py
```

Run `verify_pipeline.py` before any PR that touches `agent/graph.py` or any node.

## Project layout

```
app.py                          # Dashboard / landing page
pages/
└── 1_New_Paper.py              # New-paper flow with the three checkpoints

agent/
├── state.py                    # PaperState TypedDict + Pydantic models
├── modes.py                    # survey/empirical/term profiles
├── validators.py               # citations, budget tracker, model allowlist
├── graph.py                    # StateGraph build with 3 interrupts
├── checkpointer.py             # Postgres-backed LangGraph checkpointer singleton
├── db.py                       # Supabase CRUD: papers, paper_files, storage
├── export_pdf.py               # markdown → PDF for the download button
├── ui_helpers.py               # pure (no-streamlit) helpers, unit-tested
├── nodes/
│   ├── intake.py
│   ├── researcher.py           # ReAct sub-agent, docs-addendum when docs uploaded
│   ├── drafter.py              # per-section retrieval injects REFERENCE PASSAGES
│   ├── data_analyzer.py        # empirical mode only
│   ├── reviewer.py
│   └── finalize.py
├── prompts.py                  # per-agent + per-mode prompts (+ docs-addenda)
├── tools.py                    # web_search, wikipedia, arxiv, python_repl, document_search
└── rag.py                      # PDF / TXT / CSV → FAISS index

tests/                          # unit tests, no API calls
verify_pipeline.py              # integration harness, requires OPENAI_API_KEY
docs/supabase_setup.sql         # one-shot schema migration
```

## Privacy and persistence

- Uploaded documents are indexed in-memory as a FAISS store on `st.session_state`, and
  the raw bytes are also uploaded to Supabase Storage so the same paper can be resumed
  (the FAISS index is rebuilt on resume from the persisted blobs).
- LangGraph checkpoints, paper metadata, and file references live in Postgres.
- Restarting Streamlit clears the in-memory FAISS, but everything else survives
  because it's in Supabase. Use the Delete button on the dashboard to wipe a paper
  (removes its DB rows, storage blobs, and checkpointer state).
