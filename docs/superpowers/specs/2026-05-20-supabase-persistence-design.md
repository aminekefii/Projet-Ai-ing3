# Supabase Persistence — Design

**Status**: approved
**Date**: 2026-05-20

## Goal

Replace the project's deliberately ephemeral in-memory state with Supabase-backed persistence so that:

1. A research paper survives a Streamlit restart — both in-progress (resumable mid-checkpoint) and completed (revisitable later).
2. Uploaded source files (PDF / TXT / CSV) survive a restart and are re-attached to the paper they belong to.

This is **single-user**: no auth, no Row-Level Security, the Supabase service-role key in `.env` is enough.

## Non-goals

- Multi-user / login / RLS (future, possibly bolt-on later with one schema change).
- Migrating vector search from FAISS to `pgvector` (FAISS stays in-memory, rebuilt on demand from the persisted blobs).
- Realtime / collaborative editing of papers.
- Caching the FAISS index in Storage (re-embedding on resume is fine for the document sizes in scope).

## Architecture

Two persistence layers, two clients, one Supabase project:

```
Streamlit
   ├── LangGraph graph ──► PostgresSaver ──► psycopg pool ──► Supabase Postgres
   │                                                              ├── checkpoints, checkpoint_blobs, checkpoint_writes  (managed by LangGraph)
   │                                                              └── papers, paper_files  (ours)
   └── agent/db.py ──► supabase-py SDK ──► Supabase Postgres (REST/PostgREST)
                                  └────► Supabase Storage (paper-files bucket)
```

- `langgraph-checkpoint-postgres`'s `PostgresSaver` reads/writes its three checkpoint tables via raw psycopg — it does not speak the Supabase SDK.
- Everything else (our papers/files metadata tables, blob uploads/downloads) goes through the friendlier `supabase-py` client.
- Both clients hit the same Postgres database via different protocols; that's normal for Supabase apps.

## Database schema

All in the `public` schema. SQL lives in `docs/supabase_setup.sql`, pasted once into the Supabase SQL editor.

```sql
create table public.papers (
    id            uuid primary key,                -- == LangGraph thread_id
    topic         text not null,
    mode          text not null check (mode in ('survey', 'empirical', 'term')),
    status        text not null default 'in_progress'
                  check (status in ('in_progress', 'complete')),
    final_output  text,                            -- finalized Markdown, null until done
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index papers_status_updated_idx
    on public.papers (status, updated_at desc);

create table public.paper_files (
    id            uuid primary key default gen_random_uuid(),
    paper_id      uuid not null references public.papers(id) on delete cascade,
    file_name     text not null,
    file_size     int  not null,
    storage_path  text not null,
    uploaded_at   timestamptz not null default now()
);

create index paper_files_paper_idx on public.paper_files (paper_id);
```

**Storage bucket:** one private bucket `paper-files`, created via the Supabase dashboard. Objects are keyed `{paper_id}/{file_name}`. Deleting a paper cascades the metadata; the bucket prefix is purged in `db.delete_paper()`.

**`id` == `thread_id`** by design — one identifier across LangGraph state, the metadata row, and the storage prefix. No mapping table.

**No `user_id` column** — single-user. Adding it later is one `alter table` plus a `where user_id = ?` in three queries.

**LangGraph's three tables** (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) are created automatically by calling `PostgresSaver.setup()` once at first boot. We don't write or migrate them ourselves.

## File structure

### New files

| File | Responsibility | Public interface |
|---|---|---|
| `agent/db.py` | Supabase client singleton + CRUD on `papers`/`paper_files` + Storage upload/download | `get_client()`, `create_paper(thread_id, topic, mode)`, `update_paper_topic(thread_id, topic)`, `list_papers()`, `get_paper(thread_id)`, `mark_complete(thread_id, final_output)`, `upload_file(thread_id, uploaded_file) -> storage_path`, `list_paper_files(thread_id)`, `download_file(storage_path) -> bytes`, `delete_paper(thread_id)` |
| `agent/checkpointer.py` | Build a `PostgresSaver` bound to Supabase Postgres, call `.setup()` once, cache as module-level singleton | `get_checkpointer() -> PostgresSaver` |
| `docs/supabase_setup.sql` | The schema above. User pastes once into the Supabase SQL editor. | — |
| `tests/test_db.py` | Unit tests for `agent/db.py` with mocked Supabase client | — |
| `tests/test_checkpointer.py` | Unit tests confirming singleton behavior + missing-env-var error | — |
| `tests/integration/test_supabase_live.py` | End-to-end DB smoke test, **auto-skipped when `SUPABASE_URL` env var is absent** so CI stays clean | — |
| `.env.example` | Template for the three new env vars (no secrets) | — |

### Modified files

- **`requirements.txt`** — add `supabase>=2.0`, `langgraph-checkpoint-postgres>=2.0`, `psycopg[binary,pool]>=3.2`.
- **`agent/graph.py`** — no change. `build_graph()` already accepts `checkpointer=`; the page just passes `get_checkpointer()` instead of constructing `MemorySaver()`.
- **`app.py`** — landing page gains a "My papers" section below the mode cards. Each row is a button to resume. Mode-card click now creates the paper row in DB before switching pages.
- **`pages/1_New_Paper.py`** — five touch points:
  1. Replace `MemorySaver()` defaults init with `get_checkpointer()`.
  2. After the initial topic is captured, call `db.update_paper_topic(thread_id, topic)`.
  3. After successful FAISS indexing, also call `db.upload_file(thread_id, uploaded_file)` per file.
  4. After `final_output` is set, call `db.mark_complete(thread_id, final_output)`.
  5. At the top of the page: if `st.session_state.resume_paper_id` is set, fetch the paper row, download its file blobs from Storage, rebuild FAISS, and let the existing render logic pick up the state from `PostgresSaver`.

## User flows

```
NEW PAPER
  click "Start →" on a mode card on app.py
    → new uuid
    → db.create_paper(uuid, topic="(untitled)", mode)
    → st.session_state.thread_id = uuid
    → switch_page → New Paper page

UPLOAD FILE
  user picks file → click "📚 Index"
    → existing FAISS indexing runs (unchanged)
    → for each file, db.upload_file(thread_id, file):
        - blob → Supabase Storage at paper-files/{thread_id}/{file_name}
        - insert row into paper_files

FINALIZE
  user clicks "✅ Approve → finalize"
    → graph runs finalize_node, sets final_output
    → db.mark_complete(thread_id, final_output)
    → status='complete', updated_at=now()

RESUME
  click a row in landing-page "My papers" list
    → st.session_state.resume_paper_id = paper_id
    → switch_page → New Paper page
    → on first render:
        - db.get_paper(paper_id) → topic, mode, status
        - st.session_state.thread_id = paper_id
        - for each db.list_paper_files(paper_id): download blob, feed into FAISS
        - PostgresSaver already has the checkpoint state for this thread_id
        - existing render logic shows the right checkpoint card or the completed view
```

## Error handling

Principle: persistence is additive. Every failure leaves the user able to download whatever they've already produced.

| Failure | When | Behavior |
|---|---|---|
| Missing env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`) | App startup | `agent/db.py` and `agent/checkpointer.py` raise `RuntimeError(f"Missing env var: {name}")`. Streamlit sidebar shows a red error box pointing to `.env.example`. No graph runs until fixed. |
| Postgres connection refused | First call to `get_checkpointer()` or `db.list_papers()` | psycopg raises `OperationalError`. Page-level try/except shows `st.error("Cannot reach Supabase Postgres: <msg>")`. App stays loaded; user can fix `.env` and rerun. |
| Storage upload fails for one file | During file indexing | Per-file try/except. Failed files are dropped from `paper_files` (no orphan row), `st.warning` lists them, FAISS keeps the ones that succeeded. |
| Storage download fails on resume | Loading a past paper | Per-file try/except. Missing blobs are skipped with `st.warning("File '{name}' missing from Storage — continuing without it")`. The paper still loads; FAISS contains fewer chunks. |
| `db.mark_complete` fails on finalize | After `final_output` is set | The Markdown is already in `st.session_state` — Markdown/PDF buttons still work. Show `st.warning("Could not save paper to history: <msg>")`. No data loss. |
| LangGraph checkpoint write fails | Mid-graph-run | psycopg raises inside `graph.stream()`. Existing Streamlit exception path catches it. User clicks "Start over". |

## Testing

| Test | File | Type | Hits Supabase? |
|---|---|---|---|
| `db.upload_file` returns expected storage path | `tests/test_db.py` | Unit, mocked SDK | No |
| `db.create_paper` / `mark_complete` / `list_papers` issue correct table calls | `tests/test_db.py` | Unit, mocked SDK | No |
| `db.list_paper_files` returns rows in upload order | `tests/test_db.py` | Unit, mocked | No |
| Missing env var raises `RuntimeError` with the var name | `tests/test_db.py` | Unit | No |
| `get_checkpointer()` returns a `PostgresSaver` and is cached (singleton) | `tests/test_checkpointer.py` | Unit, monkeypatched | No |
| End-to-end DB smoke (create paper → upload → list → delete) | `tests/integration/test_supabase_live.py` | Integration | Yes — skipped if `SUPABASE_URL` absent |

Mocking is done with `unittest.mock` at the Supabase SDK boundary. The goal is to assert *what we tell Supabase to do*, not to re-test Supabase itself.

**Manual smoke test** (post-implementation):
1. Set up Supabase project, paste `docs/supabase_setup.sql`, create `paper-files` bucket, fill `.env`.
2. Start app, click a mode card, upload a file, complete a paper.
3. Stop and restart Streamlit. Confirm: paper appears in "My papers"; clicking it loads the topic, the file is re-downloaded from Storage, and the final Markdown/PDF is downloadable again.

## Dependencies to add

```
supabase>=2.0
langgraph-checkpoint-postgres>=2.0
psycopg[binary,pool]>=3.2
```

## Environment variables (`.env.example`)

```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>            # NOT the anon key
SUPABASE_DB_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
```

The user retrieves these from Supabase Dashboard → Settings → API (URL + service-role key) and Settings → Database (direct connection string).

## Out of scope (deferred)

- Multi-user / Supabase Auth / RLS policies.
- Migration from FAISS to `pgvector`.
- Caching the FAISS index itself in Storage (avoid re-embedding on resume).
- Pagination on the "My papers" list (fine until there are hundreds).
- A "delete paper" UI affordance (the function exists in `db.py` but isn't surfaced yet).
