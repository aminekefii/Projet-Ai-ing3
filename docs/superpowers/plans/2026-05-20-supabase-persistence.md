# Supabase Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the project's ephemeral in-memory state with Supabase persistence so threads (LangGraph checkpoints + paper metadata) and uploaded files survive a Streamlit restart, and past papers are resumable from a landing-page list.

**Architecture:** Single Supabase project hosting (a) Postgres tables — three managed by LangGraph's `PostgresSaver`, plus two we own (`papers`, `paper_files`) — and (b) one private Storage bucket (`paper-files`). LangGraph speaks raw psycopg; metadata CRUD and Storage I/O go through the `supabase-py` SDK. Single-user, no auth, no RLS.

**Tech Stack:** Python, Streamlit, LangGraph, `supabase-py`, `langgraph-checkpoint-postgres`, `psycopg[binary,pool]`, pytest with `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-05-20-supabase-persistence-design.md`

---

## Phases

1. **Setup** — deps, env template, schema doc (Tasks 1–2).
2. **Connection layer (TDD)** — `agent/db.py` skeleton + `agent/checkpointer.py` singleton (Tasks 3–4).
3. **Data access (TDD)** — papers CRUD + files/storage CRUD in `agent/db.py` (Tasks 5–6).
4. **UI wiring — persist** — PostgresSaver in the page, create-paper on card click, update-topic + mark-complete, upload-files-to-Storage (Tasks 7–10).
5. **UI wiring — resume** — "My papers" list on landing page + resume flow on New Paper page (Tasks 11–12).
6. **Integration + manual smoke** — live integration test (env-gated), manual end-to-end check (Tasks 13–14).

## File Structure

**New files**
- `agent/db.py` — Supabase client singleton + papers/files CRUD + Storage I/O. ~150 lines.
- `agent/checkpointer.py` — `get_checkpointer() -> PostgresSaver` cached singleton. ~30 lines.
- `docs/supabase_setup.sql` — schema migration the user pastes into Supabase SQL editor.
- `.env.example` — env-var template.
- `tests/test_db.py` — unit tests for `agent/db.py` (Supabase SDK mocked).
- `tests/test_checkpointer.py` — unit tests for `agent/checkpointer.py`.
- `tests/integration/__init__.py` — empty marker.
- `tests/integration/test_supabase_live.py` — env-gated end-to-end DB smoke test.

**Modified files**
- `requirements.txt` — three new lines.
- `app.py` — mode-card click creates a paper row; new "My papers" section below the cards.
- `pages/1_New_Paper.py` — five touch points (checkpointer, update topic, mark complete, upload files, resume flow).

**Unchanged but reused:** `agent/graph.py` already accepts a `checkpointer=` argument — no change needed.

---

## Phase 1 — Setup

### Task 1: Add dependencies and env template

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\requirements.txt`
- Create: `C:\Users\amine\Desktop\ProjetAI\.env.example`

- [ ] **Step 1: Add the three dependencies**

Open `requirements.txt`. Replace the file with:

```
streamlit>=1.40.0
langchain>=0.3.0
langchain-core>=0.3.0
langchain-openai>=0.3.0
langchain-community>=0.3.0
langchain-experimental>=0.3.0
langgraph>=0.3.0
langgraph-checkpoint-postgres>=2.0
ddgs>=9.0.0
wikipedia>=1.4.0
arxiv>=2.1.0
python-dotenv>=1.0.0

# RAG over uploaded documents
pypdf>=5.1.0
fastembed>=0.4.0
faiss-cpu>=1.9.0

# Supabase persistence
supabase>=2.0
psycopg[binary,pool]>=3.2

pydantic>=2.9.0
tenacity>=9.0.0
markdown-pdf>=1.3
pytest>=8.3.0
```

- [ ] **Step 2: Install the new dependencies**

Run: `pip install -r requirements.txt`

Expected: successful install of `supabase`, `psycopg[binary,pool]`, `langgraph-checkpoint-postgres` and their transitive deps. Existing packages already satisfied.

- [ ] **Step 3: Verify imports work**

Run:
```
python -c "import supabase; from psycopg_pool import ConnectionPool; from langgraph.checkpoint.postgres import PostgresSaver; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 4: Create `.env.example`**

Create `C:\Users\amine\Desktop\ProjetAI\.env.example` with:

```
# OpenAI — required for the LLM
OPENAI_API_KEY=sk-...

# Supabase — required for persistence
# Get these from https://supabase.com/dashboard → your project → Settings
# - URL + service_role key: Settings → API
# - DB URL: Settings → Database → Connection string → URI
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
SUPABASE_DB_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example
git commit -m "deps: add supabase, psycopg, langgraph-checkpoint-postgres + env template"
```

---

### Task 2: Add the SQL schema migration

**Files:**
- Create: `C:\Users\amine\Desktop\ProjetAI\docs\supabase_setup.sql`

- [ ] **Step 1: Write the schema file**

Create `docs/supabase_setup.sql`:

```sql
-- Supabase schema for ProjetAI research-paper agent.
-- Paste this into the Supabase Dashboard → SQL Editor → New Query → Run.
-- Then create a private Storage bucket named 'paper-files' from the dashboard.

-- ---------- papers ----------
create table if not exists public.papers (
    id            uuid primary key,
    topic         text not null,
    mode          text not null check (mode in ('survey', 'empirical', 'term')),
    status        text not null default 'in_progress'
                  check (status in ('in_progress', 'complete')),
    final_output  text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index if not exists papers_status_updated_idx
    on public.papers (status, updated_at desc);

-- ---------- paper_files ----------
create table if not exists public.paper_files (
    id            uuid primary key default gen_random_uuid(),
    paper_id      uuid not null references public.papers(id) on delete cascade,
    file_name     text not null,
    file_size     int  not null,
    storage_path  text not null,
    uploaded_at   timestamptz not null default now()
);

create index if not exists paper_files_paper_idx on public.paper_files (paper_id);
```

- [ ] **Step 2: Commit**

```bash
git add docs/supabase_setup.sql
git commit -m "docs: add Supabase schema migration SQL"
```

---

## Phase 2 — Connection layer (TDD)

### Task 3: `agent/db.py` skeleton + env check (TDD)

**Files:**
- Create: `C:\Users\amine\Desktop\ProjetAI\agent\db.py`
- Create: `C:\Users\amine\Desktop\ProjetAI\tests\test_db.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db.py`:

```python
"""Unit tests for agent.db — Supabase client + papers/files CRUD."""
from unittest.mock import MagicMock, patch

import pytest


def test_missing_env_var_raises_runtime_error(monkeypatch):
    """get_client() must fail loudly with the exact missing var name."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    # Re-import to reset the module-level cache.
    import importlib

    import agent.db as db
    importlib.reload(db)

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        db.get_client()


def test_get_client_caches_singleton(monkeypatch):
    """Repeated get_client() calls return the same client object."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    import importlib

    import agent.db as db
    importlib.reload(db)

    fake_client = MagicMock()
    with patch("agent.db.create_client", return_value=fake_client) as create:
        first = db.get_client()
        second = db.get_client()

    assert first is second
    assert create.call_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.db'`.

- [ ] **Step 3: Write the minimal implementation**

Create `agent/db.py`:

```python
"""Supabase client + papers/files CRUD + Storage I/O."""
from __future__ import annotations

import os
from typing import Optional

from supabase import Client, create_client

_PAPERS_TABLE = "papers"
_FILES_TABLE = "paper_files"
_BUCKET = "paper-files"

_client: Optional[Client] = None


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def get_client() -> Client:
    """Return the cached Supabase client, building it on first call."""
    global _client
    if _client is None:
        url = _require_env("SUPABASE_URL")
        key = _require_env("SUPABASE_SERVICE_KEY")
        _client = create_client(url, key)
    return _client
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/db.py tests/test_db.py
git commit -m "feat(db): add Supabase client singleton with env validation"
```

---

### Task 4: `agent/checkpointer.py` singleton (TDD)

**Files:**
- Create: `C:\Users\amine\Desktop\ProjetAI\agent\checkpointer.py`
- Create: `C:\Users\amine\Desktop\ProjetAI\tests\test_checkpointer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_checkpointer.py`:

```python
"""Unit tests for agent.checkpointer — Postgres-backed LangGraph checkpointer."""
from unittest.mock import MagicMock, patch

import pytest


def test_missing_db_url_raises(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    import importlib

    import agent.checkpointer as cp
    importlib.reload(cp)

    with pytest.raises(RuntimeError, match="SUPABASE_DB_URL"):
        cp.get_checkpointer()


def test_get_checkpointer_returns_postgres_saver_singleton(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://u:p@h/db")

    import importlib

    import agent.checkpointer as cp
    importlib.reload(cp)

    fake_saver = MagicMock()
    fake_pool = MagicMock()

    with patch("agent.checkpointer.ConnectionPool", return_value=fake_pool) as pool_cls, \
         patch("agent.checkpointer.PostgresSaver", return_value=fake_saver) as saver_cls:
        first = cp.get_checkpointer()
        second = cp.get_checkpointer()

    assert first is fake_saver
    assert first is second
    assert pool_cls.call_count == 1
    assert saver_cls.call_count == 1
    fake_saver.setup.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_checkpointer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.checkpointer'`.

- [ ] **Step 3: Write the minimal implementation**

Create `agent/checkpointer.py`:

```python
"""Postgres-backed LangGraph checkpointer (Supabase-hosted)."""
from __future__ import annotations

import os
from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

_CONNECTION_KWARGS = {"autocommit": True, "prepare_threshold": 0}
_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> PostgresSaver:
    """Return the cached PostgresSaver, building it (and creating tables) on first call."""
    global _checkpointer
    if _checkpointer is None:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            raise RuntimeError("Missing env var: SUPABASE_DB_URL")
        pool = ConnectionPool(db_url, kwargs=_CONNECTION_KWARGS, open=True)
        saver = PostgresSaver(pool)
        saver.setup()
        _checkpointer = saver
    return _checkpointer
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_checkpointer.py -v`
Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/checkpointer.py tests/test_checkpointer.py
git commit -m "feat(checkpointer): add Postgres-backed LangGraph checkpointer singleton"
```

---

## Phase 3 — Data access (TDD)

### Task 5: papers CRUD in `agent/db.py` (TDD)

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\agent\db.py`
- Modify: `C:\Users\amine\Desktop\ProjetAI\tests\test_db.py`

- [ ] **Step 1: Add failing tests for papers CRUD**

Append to `tests/test_db.py`:

```python
# ---------- papers CRUD ----------

@pytest.fixture
def patched_client(monkeypatch):
    """Return a MagicMock standing in for the Supabase client, with env vars set."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    import importlib

    import agent.db as db
    importlib.reload(db)

    client = MagicMock()
    with patch("agent.db.create_client", return_value=client):
        # warm the cache
        db.get_client()
        yield client, db


def test_create_paper_inserts_row(patched_client):
    client, db = patched_client
    db.create_paper("abc-123", "Photosynthesis", "term")

    client.table.assert_called_with("papers")
    insert = client.table.return_value.insert
    insert.assert_called_once()
    row = insert.call_args[0][0]
    assert row["id"] == "abc-123"
    assert row["topic"] == "Photosynthesis"
    assert row["mode"] == "term"
    insert.return_value.execute.assert_called_once()


def test_update_paper_topic_updates_row(patched_client):
    client, db = patched_client
    db.update_paper_topic("abc-123", "New Topic")

    client.table.assert_called_with("papers")
    update = client.table.return_value.update
    update.assert_called_once()
    args = update.call_args[0][0]
    assert args["topic"] == "New Topic"
    assert "updated_at" in args
    update.return_value.eq.assert_called_with("id", "abc-123")


def test_mark_complete_sets_status_and_output(patched_client):
    client, db = patched_client
    db.mark_complete("abc-123", "# Final paper\n\n## Intro\n…")

    client.table.assert_called_with("papers")
    update = client.table.return_value.update
    args = update.call_args[0][0]
    assert args["status"] == "complete"
    assert args["final_output"].startswith("# Final paper")
    update.return_value.eq.assert_called_with("id", "abc-123")


def test_get_paper_returns_row(patched_client):
    client, db = patched_client
    fake_row = {"id": "abc-123", "topic": "X", "mode": "term", "status": "complete",
                "final_output": "# X", "created_at": "now", "updated_at": "now"}
    response = MagicMock()
    response.data = [fake_row]
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = response

    got = db.get_paper("abc-123")
    assert got == fake_row


def test_get_paper_returns_none_when_missing(patched_client):
    client, db = patched_client
    response = MagicMock()
    response.data = []
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = response

    assert db.get_paper("missing") is None


def test_list_papers_returns_rows_ordered(patched_client):
    client, db = patched_client
    rows = [{"id": "a", "topic": "A"}, {"id": "b", "topic": "B"}]
    response = MagicMock()
    response.data = rows
    client.table.return_value.select.return_value.order.return_value.execute.return_value = response

    got = db.list_papers()
    assert got == rows
    client.table.return_value.select.assert_called_with("*")
    client.table.return_value.select.return_value.order.assert_called_with(
        "updated_at", desc=True
    )


def test_delete_paper_cascades_to_files_and_storage(patched_client):
    client, db = patched_client
    # paper_files rows for this paper
    files_response = MagicMock()
    files_response.data = [{"storage_path": "abc/file1.pdf"},
                           {"storage_path": "abc/file2.csv"}]
    (client.table.return_value.select.return_value
        .eq.return_value.execute.return_value) = files_response

    db.delete_paper("abc-123")

    # Storage purge
    client.storage.from_.assert_any_call("paper-files")
    client.storage.from_.return_value.remove.assert_called_with(
        ["abc/file1.pdf", "abc/file2.csv"]
    )

    # Cascade deletes the papers row (and paper_files via FK ON DELETE CASCADE)
    client.table.assert_any_call("papers")
    delete = client.table.return_value.delete
    delete.return_value.eq.assert_called_with("id", "abc-123")
```

- [ ] **Step 2: Run new tests, confirm they fail**

Run: `pytest tests/test_db.py -v`
Expected: the two existing tests still PASS; the seven new ones FAIL with `AttributeError: module 'agent.db' has no attribute 'create_paper'` (and similar).

- [ ] **Step 3: Implement the CRUD functions**

Append to `agent/db.py`:

```python
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_paper(thread_id: str, topic: str, mode: str) -> None:
    """Insert a new paper row in 'in_progress' status."""
    get_client().table(_PAPERS_TABLE).insert({
        "id": thread_id,
        "topic": topic,
        "mode": mode,
        "status": "in_progress",
    }).execute()


def update_paper_topic(thread_id: str, topic: str) -> None:
    """Update the topic (called once the user types it in)."""
    get_client().table(_PAPERS_TABLE).update({
        "topic": topic,
        "updated_at": _now_iso(),
    }).eq("id", thread_id).execute()


def mark_complete(thread_id: str, final_output: str) -> None:
    """Mark a paper complete and save its finalized Markdown."""
    get_client().table(_PAPERS_TABLE).update({
        "status": "complete",
        "final_output": final_output,
        "updated_at": _now_iso(),
    }).eq("id", thread_id).execute()


def get_paper(thread_id: str) -> Optional[dict]:
    """Return the paper row, or None if not found."""
    response = (get_client().table(_PAPERS_TABLE)
                .select("*")
                .eq("id", thread_id)
                .execute())
    return response.data[0] if response.data else None


def list_papers() -> list[dict]:
    """Return all paper rows, most recently updated first."""
    response = (get_client().table(_PAPERS_TABLE)
                .select("*")
                .order("updated_at", desc=True)
                .execute())
    return response.data or []


def delete_paper(thread_id: str) -> None:
    """Delete a paper, its file metadata (via ON DELETE CASCADE), and its Storage blobs."""
    client = get_client()
    files = (client.table(_FILES_TABLE)
             .select("storage_path")
             .eq("paper_id", thread_id)
             .execute())
    paths = [row["storage_path"] for row in (files.data or [])]
    if paths:
        client.storage.from_(_BUCKET).remove(paths)
    client.table(_PAPERS_TABLE).delete().eq("id", thread_id).execute()
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS, 9 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/db.py tests/test_db.py
git commit -m "feat(db): add papers CRUD (create/get/list/update/complete/delete)"
```

---

### Task 6: files + Storage in `agent/db.py` (TDD)

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\agent\db.py`
- Modify: `C:\Users\amine\Desktop\ProjetAI\tests\test_db.py`

- [ ] **Step 1: Add failing tests for files + storage**

Append to `tests/test_db.py`:

```python
# ---------- files + storage ----------

class _FakeUploadedFile:
    """Stand-in for a streamlit.runtime.uploaded_file_manager.UploadedFile."""
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload
        self.size = len(payload)
    def getvalue(self) -> bytes:
        return self._payload


def test_upload_file_writes_blob_and_inserts_row(patched_client):
    client, db = patched_client
    f = _FakeUploadedFile("notes.pdf", b"%PDF-1.7 fake")

    path = db.upload_file("abc-123", f)

    assert path == "abc-123/notes.pdf"

    # Storage call
    client.storage.from_.assert_any_call("paper-files")
    client.storage.from_.return_value.upload.assert_called_once()
    upload_args = client.storage.from_.return_value.upload.call_args
    assert upload_args.kwargs.get("path") == "abc-123/notes.pdf" \
        or upload_args.args[0] == "abc-123/notes.pdf"

    # Metadata insert
    client.table.assert_any_call("paper_files")
    insert = client.table.return_value.insert
    row = insert.call_args[0][0]
    assert row["paper_id"] == "abc-123"
    assert row["file_name"] == "notes.pdf"
    assert row["file_size"] == len(b"%PDF-1.7 fake")
    assert row["storage_path"] == "abc-123/notes.pdf"


def test_list_paper_files_returns_rows_in_upload_order(patched_client):
    client, db = patched_client
    rows = [{"file_name": "a.pdf"}, {"file_name": "b.pdf"}]
    response = MagicMock()
    response.data = rows
    (client.table.return_value.select.return_value
        .eq.return_value.order.return_value.execute.return_value) = response

    got = db.list_paper_files("abc-123")
    assert got == rows
    client.table.return_value.select.return_value.eq.assert_called_with(
        "paper_id", "abc-123"
    )
    client.table.return_value.select.return_value.eq.return_value.order \
        .assert_called_with("uploaded_at")


def test_download_file_returns_blob_bytes(patched_client):
    client, db = patched_client
    client.storage.from_.return_value.download.return_value = b"%PDF-blob"

    blob = db.download_file("abc-123/notes.pdf")
    assert blob == b"%PDF-blob"
    client.storage.from_.assert_any_call("paper-files")
    client.storage.from_.return_value.download.assert_called_with("abc-123/notes.pdf")
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_db.py -v`
Expected: previous 9 still pass; new 3 fail with `AttributeError` on `upload_file` / `list_paper_files` / `download_file`.

- [ ] **Step 3: Implement files + storage functions**

Append to `agent/db.py`:

```python
def upload_file(thread_id: str, uploaded_file) -> str:
    """Upload a Streamlit UploadedFile to Storage and record metadata.

    Returns the storage path of the uploaded blob.
    """
    payload = uploaded_file.getvalue()
    storage_path = f"{thread_id}/{uploaded_file.name}"

    client = get_client()
    client.storage.from_(_BUCKET).upload(
        path=storage_path,
        file=payload,
        file_options={"upsert": "true"},
    )
    client.table(_FILES_TABLE).insert({
        "paper_id": thread_id,
        "file_name": uploaded_file.name,
        "file_size": len(payload),
        "storage_path": storage_path,
    }).execute()
    return storage_path


def list_paper_files(thread_id: str) -> list[dict]:
    """Return all file rows for a paper, oldest upload first."""
    response = (get_client().table(_FILES_TABLE)
                .select("*")
                .eq("paper_id", thread_id)
                .order("uploaded_at")
                .execute())
    return response.data or []


def download_file(storage_path: str) -> bytes:
    """Download a blob from Storage by its path."""
    return get_client().storage.from_(_BUCKET).download(storage_path)
```

- [ ] **Step 4: Run tests, confirm all pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS, 12 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/db.py tests/test_db.py
git commit -m "feat(db): add file upload/download + paper_files CRUD"
```

---

## Phase 4 — UI wiring: persist

### Task 7: Use PostgresSaver in `pages/1_New_Paper.py`

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py`
- Modify: `C:\Users\amine\Desktop\ProjetAI\app.py`

- [ ] **Step 1: Replace MemorySaver in the New Paper page**

In `pages/1_New_Paper.py`, find the imports near the top:

```python
from langgraph.checkpoint.memory import MemorySaver
```

Replace with:

```python
from agent.checkpointer import get_checkpointer
```

Then find the `defaults` dict (currently around line 17):

```python
defaults = {
    "thread_id": str(uuid.uuid4()),
    "checkpointer": MemorySaver(),
    ...
}
```

Replace `"checkpointer": MemorySaver(),` with `"checkpointer": get_checkpointer(),`. Also remove the now-unused `MemorySaver` import line if it's not used elsewhere in the file.

Then find the "Start over" button block (around line 60):

```python
if st.button("🗑️ Start over", use_container_width=True):
    for k, v in defaults.items():
        st.session_state[k] = v if not callable(v) else v
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.checkpointer = MemorySaver()
    st.rerun()
```

Replace the inner `MemorySaver()` with `get_checkpointer()`.

- [ ] **Step 2: Replace MemorySaver in the landing page**

In `app.py`, find the imports:

```python
from langgraph.checkpoint.memory import MemorySaver
```

Replace with:

```python
from agent.checkpointer import get_checkpointer
```

Then find the `defaults` dict (around line 14):

```python
defaults = {
    "thread_id": str(uuid.uuid4()),
    "checkpointer": MemorySaver(),
    ...
}
```

Replace `"checkpointer": MemorySaver(),` with `"checkpointer": get_checkpointer(),`.

Find the mode-card click block (around line 112):

```python
if st.button(...):
    st.session_state.mode = mode["key"]
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.checkpointer = MemorySaver()
    ...
```

Replace `MemorySaver()` with `get_checkpointer()`.

- [ ] **Step 3: Run the unit tests to confirm no regression**

Run: `pytest -q`
Expected: all existing tests still pass. `tests/test_checkpointer.py` and `tests/test_db.py` continue to pass — the page changes are not exercised here.

- [ ] **Step 4: Commit**

```bash
git add pages/1_New_Paper.py app.py
git commit -m "feat(ui): use Postgres-backed checkpointer for thread persistence"
```

---

### Task 8: Create paper row on mode-card click in `app.py`

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\app.py`

- [ ] **Step 1: Add db import and wire create_paper into the mode-card button**

In `app.py`, add to the top-level imports:

```python
from agent import db
```

Find the mode-card click block (around lines 112–125):

```python
if st.button(
    f"Start →",
    key=f"start_{mode['key']}",
    use_container_width=True,
    type="primary",
):
    st.session_state.mode = mode["key"]
    # Reset paper state so a fresh paper starts cleanly
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.checkpointer = get_checkpointer()
    st.session_state.pending_checkpoint = None
    st.session_state.run_started = False
    st.session_state.trace = []
    st.switch_page("pages/1_New_Paper.py")
```

Replace with:

```python
if st.button(
    f"Start →",
    key=f"start_{mode['key']}",
    use_container_width=True,
    type="primary",
):
    new_id = str(uuid.uuid4())
    try:
        db.create_paper(new_id, topic="(untitled)", mode=mode["key"])
    except Exception as e:
        st.error(f"Could not reach Supabase: {e}")
        st.stop()
    st.session_state.mode = mode["key"]
    st.session_state.thread_id = new_id
    st.session_state.checkpointer = get_checkpointer()
    st.session_state.pending_checkpoint = None
    st.session_state.run_started = False
    st.session_state.trace = []
    st.switch_page("pages/1_New_Paper.py")
```

- [ ] **Step 2: Run unit tests, confirm no regression**

Run: `pytest -q`
Expected: all tests still pass (this is a pure UI change with no test coverage; verify only that nothing else broke).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(ui): create papers row on mode-card click"
```

---

### Task 9: Update topic + mark complete in `pages/1_New_Paper.py`

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py`

- [ ] **Step 1: Add db import at the top**

In `pages/1_New_Paper.py`, add to the top-level imports (next to the existing `from agent.graph import …`):

```python
from agent import db
```

- [ ] **Step 2: Persist the topic after the user submits it**

Find the chat_input block at the bottom of the file (around line 234):

```python
topic = st.chat_input("Paper topic (e.g. 'Transformer attention mechanisms')")
if topic:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Set OPENAI_API_KEY in .env first.")
        st.stop()
    st.session_state.trace.append({"kind": "user", "content": topic})
    st.session_state.run_started = True
    with st.spinner("Generating outline…"):
        ...
```

Insert a `db.update_paper_topic` call right after `st.session_state.run_started = True`:

```python
topic = st.chat_input("Paper topic (e.g. 'Transformer attention mechanisms')")
if topic:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Set OPENAI_API_KEY in .env first.")
        st.stop()
    st.session_state.trace.append({"kind": "user", "content": topic})
    st.session_state.run_started = True
    try:
        db.update_paper_topic(st.session_state.thread_id, topic)
    except Exception as e:
        st.warning(f"Could not save topic to history: {e}")
    with st.spinner("Generating outline…"):
        ...
```

- [ ] **Step 3: Persist `final_output` when the paper is complete**

Find the success block (around lines 226–246):

```python
final = snapshot.values.get("final_output")
if final:
    st.success("📑 Paper complete")
    col_md, col_pdf = st.columns(2)
    ...
```

Insert a `db.mark_complete` call right after the `if final:` line and before `st.success(...)`:

```python
final = snapshot.values.get("final_output")
if final:
    if not st.session_state.get("_persisted_complete"):
        try:
            db.mark_complete(st.session_state.thread_id, final)
            st.session_state._persisted_complete = True
        except Exception as e:
            st.warning(f"Could not save paper to history: {e}")
    st.success("📑 Paper complete")
    col_md, col_pdf = st.columns(2)
    ...
```

The `_persisted_complete` flag prevents repeated UPDATEs on every Streamlit re-render after the paper finishes.

- [ ] **Step 4: Run unit tests, confirm no regression**

Run: `pytest -q`
Expected: all tests still pass.

- [ ] **Step 5: Commit**

```bash
git add pages/1_New_Paper.py
git commit -m "feat(ui): persist paper topic and mark complete to Supabase"
```

---

### Task 10: Upload files to Supabase Storage on indexing

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py`

- [ ] **Step 1: Wire `db.upload_file` into the file-indexing sidebar**

In `pages/1_New_Paper.py`, find the index block in the sidebar (around lines 78–87):

```python
if uploaded and st.button("📚 Index", use_container_width=True):
    from agent.rag import index_uploaded_files
    with st.spinner("Indexing…"):
        vs, summary = index_uploaded_files(uploaded)
    if vs is None:
        st.warning("No usable text extracted.")
    else:
        st.session_state.vectorstore = vs
        st.session_state.indexed_files = summary
        st.success(f"Indexed {len(summary)} file(s).")
```

Replace with:

```python
if uploaded and st.button("📚 Index", use_container_width=True):
    from agent.rag import index_uploaded_files
    with st.spinner("Indexing…"):
        vs, summary = index_uploaded_files(uploaded)
    if vs is None:
        st.warning("No usable text extracted.")
    else:
        st.session_state.vectorstore = vs
        st.session_state.indexed_files = summary
        # Persist blobs to Supabase Storage so they survive a restart.
        upload_failures = []
        for f in uploaded:
            try:
                db.upload_file(st.session_state.thread_id, f)
            except Exception as e:
                upload_failures.append((f.name, str(e)))
        if upload_failures:
            for name, err in upload_failures:
                st.warning(f"Could not save '{name}' to Storage: {err}")
        st.success(f"Indexed {len(summary)} file(s).")
```

- [ ] **Step 2: Run unit tests, confirm no regression**

Run: `pytest -q`
Expected: all tests still pass.

- [ ] **Step 3: Commit**

```bash
git add pages/1_New_Paper.py
git commit -m "feat(ui): upload indexed files to Supabase Storage"
```

---

## Phase 5 — UI wiring: resume

### Task 11: "My papers" list on the landing page

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\app.py`

- [ ] **Step 1: Add a "My papers" section below the mode cards**

In `app.py`, find the bottom of the file. The existing code ends with:

```python
st.divider()
st.caption(
    "📖 At each checkpoint (outline → sources → draft) you approve or edit before the graph continues. "
    "State persists for the lifetime of this Streamlit server."
)
```

Replace that block with:

```python
st.divider()

# --- My papers ---
st.markdown("## 📂 My papers")
try:
    rows = db.list_papers()
except Exception as e:
    st.error(f"Could not reach Supabase: {e}")
    rows = []

if not rows:
    st.caption("No saved papers yet. Pick a mode above to start one.")
else:
    for row in rows:
        status_icon = "✅" if row["status"] == "complete" else "✏️"
        label = f"{status_icon}  **{row['topic']}**  ·  _{row['mode']}_  ·  {row['updated_at'][:10]}"
        if st.button(label, key=f"resume_{row['id']}", use_container_width=True):
            st.session_state.resume_paper_id = row["id"]
            st.switch_page("pages/1_New_Paper.py")

st.divider()
st.caption(
    "📖 At each checkpoint (outline → sources → draft) you approve or edit before the graph continues. "
    "Threads and uploaded files persist in Supabase."
)
```

- [ ] **Step 2: Run unit tests, confirm no regression**

Run: `pytest -q`
Expected: all tests still pass.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(ui): add 'My papers' list to landing page"
```

---

### Task 12: Resume flow in `pages/1_New_Paper.py`

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py`

- [ ] **Step 1: Add an `io.BytesIO` import at the top**

In `pages/1_New_Paper.py`, near the top imports, add:

```python
import io
```

- [ ] **Step 2: Add the resume block right before the existing "Main flow" comment**

Find the line `# --- Main flow ---` (around line 217). Insert this block immediately before it:

```python
# --- Resume an existing paper if requested ---
resume_id = st.session_state.pop("resume_paper_id", None)
if resume_id:
    paper = db.get_paper(resume_id)
    if paper is None:
        st.error(f"Paper {resume_id[:8]}… not found.")
        st.stop()
    st.session_state.thread_id = resume_id
    st.session_state.mode = paper["mode"]
    st.session_state.trace = [{"kind": "user", "content": paper["topic"]}]
    st.session_state.run_started = True
    st.session_state.pending_checkpoint = None
    st.session_state._persisted_complete = (paper["status"] == "complete")

    # Re-download persisted files and rebuild FAISS in-memory.
    file_rows = db.list_paper_files(resume_id)
    if file_rows:
        from agent.rag import index_uploaded_files

        class _ResumedFile:
            def __init__(self, name, payload):
                self.name = name
                self._buf = io.BytesIO(payload)
                self.size = len(payload)
            def getvalue(self):
                return self._buf.getvalue()
            def read(self, *args, **kwargs):
                return self._buf.read(*args, **kwargs)
            def seek(self, *args, **kwargs):
                return self._buf.seek(*args, **kwargs)

        resumed_files = []
        for row in file_rows:
            try:
                blob = db.download_file(row["storage_path"])
                resumed_files.append(_ResumedFile(row["file_name"], blob))
            except Exception as e:
                st.warning(f"File '{row['file_name']}' missing from Storage — continuing without it ({e})")
        if resumed_files:
            with st.spinner("Re-indexing saved files…"):
                vs, summary = index_uploaded_files(resumed_files)
            if vs is not None:
                st.session_state.vectorstore = vs
                st.session_state.indexed_files = summary

    # Sync the pending checkpoint from PostgresSaver-backed graph state.
    graph = build_graph(
        model_name=DEFAULT_MODEL,
        vectorstore=st.session_state.vectorstore,
        checkpointer=st.session_state.checkpointer,
    )
    snapshot = graph.get_state({"configurable": {"thread_id": resume_id}})
    if snapshot.next:
        st.session_state.pending_checkpoint = snapshot.next[0]
```

- [ ] **Step 3: Run unit tests, confirm no regression**

Run: `pytest -q`
Expected: all tests still pass.

- [ ] **Step 4: Commit**

```bash
git add pages/1_New_Paper.py
git commit -m "feat(ui): resume past papers from landing-page list"
```

---

## Phase 6 — Integration + manual smoke

### Task 13: Env-gated integration smoke test

**Files:**
- Create: `C:\Users\amine\Desktop\ProjetAI\tests\integration\__init__.py`
- Create: `C:\Users\amine\Desktop\ProjetAI\tests\integration\test_supabase_live.py`

- [ ] **Step 1: Create the `integration` package marker**

Create empty file `C:\Users\amine\Desktop\ProjetAI\tests\integration\__init__.py` (zero bytes).

- [ ] **Step 2: Create the live test, gated by env**

Create `C:\Users\amine\Desktop\ProjetAI\tests\integration\test_supabase_live.py`:

```python
"""End-to-end Supabase smoke test. Auto-skipped when SUPABASE_URL is unset.

This actually hits Supabase. Run after you've created the project and bucket:
  pytest tests/integration -v
"""
import os
import uuid

import pytest

if not os.getenv("SUPABASE_URL"):
    pytest.skip("SUPABASE_URL not set — skipping live Supabase test",
                allow_module_level=True)

from agent import db  # noqa: E402


class _Blob:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload
        self.size = len(payload)
    def getvalue(self) -> bytes:
        return self._payload


def test_full_paper_lifecycle():
    thread_id = str(uuid.uuid4())

    db.create_paper(thread_id, topic="(untitled)", mode="term")
    try:
        db.update_paper_topic(thread_id, "Photosynthesis")
        path = db.upload_file(thread_id, _Blob("notes.txt", b"hello supabase"))
        assert path == f"{thread_id}/notes.txt"

        files = db.list_paper_files(thread_id)
        assert len(files) == 1
        assert files[0]["file_name"] == "notes.txt"

        blob = db.download_file(path)
        assert blob == b"hello supabase"

        db.mark_complete(thread_id, "# Done")
        paper = db.get_paper(thread_id)
        assert paper["status"] == "complete"
        assert paper["topic"] == "Photosynthesis"
        assert paper["final_output"] == "# Done"

        listed = db.list_papers()
        assert any(p["id"] == thread_id for p in listed)
    finally:
        db.delete_paper(thread_id)
```

- [ ] **Step 3: Confirm the test is collected and skipped without env**

Run: `pytest tests/integration -v`
Expected without env: `1 skipped` with reason "SUPABASE_URL not set". With env + a configured Supabase project: should pass end-to-end.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_supabase_live.py
git commit -m "test(integration): add env-gated Supabase smoke test"
```

---

### Task 14: Manual end-to-end smoke test

**Files:** none — verification only.

- [ ] **Step 1: Supabase setup (one-time)**

In the Supabase dashboard:
1. Create a new project at https://supabase.com/dashboard (free tier is fine).
2. Settings → API: copy the Project URL and the `service_role` key.
3. Settings → Database → Connection string → URI: copy the direct connection string. Substitute the real password where it says `[YOUR-PASSWORD]`.
4. SQL Editor → New query → paste `docs/supabase_setup.sql` → Run.
5. Storage → Create bucket → name `paper-files` → toggle **Private** (uncheck Public) → Create.
6. Fill `.env` (in the project root, copy from `.env.example`) with `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`.

- [ ] **Step 2: Start the app**

Run: `streamlit run app.py`
Expected: dashboard loads at http://localhost:8501 with no Supabase errors in the sidebar.

- [ ] **Step 3: New-paper flow**

Pick **Term Paper**, give a small topic like "Photosynthesis basics", upload one small text or PDF file, approve outline → sources → draft. Confirm the paper finalizes and the Markdown / PDF buttons appear.

- [ ] **Step 4: Verify persistence in Supabase**

In the Supabase dashboard:
- Table Editor → `papers`: one row, `status='complete'`, `final_output` populated.
- Table Editor → `paper_files`: one row, `paper_id` matching the paper above.
- Storage → `paper-files`: one folder named after the paper UUID, containing the uploaded file.

- [ ] **Step 5: Restart-and-resume flow**

Stop Streamlit (Ctrl+C). Restart: `streamlit run app.py`. The landing page should now show a "My papers" section with the paper you just made. Click it. Confirm:
- The page loads with the original topic.
- The uploaded file appears in "Indexed files".
- The final Markdown is downloadable.
- The PDF download still works.

- [ ] **Step 6: Stop the server**

Ctrl+C in the terminal.

---

## Self-Review (already applied)

**Spec coverage:**
- Architecture: Task 4 (PostgresSaver) + Task 3 (Supabase client).
- Schema: Task 2 (SQL migration file).
- `agent/db.py` interface (10 functions): Task 3 (`get_client`), Task 5 (`create_paper`, `update_paper_topic`, `mark_complete`, `get_paper`, `list_papers`, `delete_paper`), Task 6 (`upload_file`, `list_paper_files`, `download_file`).
- `agent/checkpointer.py`: Task 4.
- `app.py` changes: Tasks 7, 8, 11.
- `pages/1_New_Paper.py` changes (five touch points): Tasks 7, 9 (topic + complete), 10 (upload), 12 (resume).
- Three user flows (new / upload / resume / finalize): Tasks 8, 10, 12, 9 respectively.
- Error-handling rows in spec: Task 3 (missing-env), Task 4 (missing-env), Task 8 (try/except around create_paper), Task 9 (try/except around topic + complete), Task 10 (per-file try/except), Task 11 (try/except around list_papers), Task 12 (per-file try/except around download).
- Tests in spec: Tasks 3–6 cover all unit tests; Task 13 covers the integration test.
- Dependencies: Task 1.
- Env vars: Task 1 (`.env.example`).
- Setup steps for Supabase dashboard: Task 14 Step 1.

**Placeholder scan:** no TBD/TODO; every step has concrete code or commands.

**Type/signature consistency:**
- `create_paper(thread_id, topic, mode)` — same signature in tests, implementation, and the `app.py` call site.
- `update_paper_topic(thread_id, topic)` — same in tests, implementation, and `pages/1_New_Paper.py`.
- `mark_complete(thread_id, final_output)` — same in tests, implementation, and `pages/1_New_Paper.py`.
- `upload_file(thread_id, uploaded_file) -> storage_path` — same in tests, implementation, and `pages/1_New_Paper.py` (passed Streamlit `UploadedFile` and a custom `_ResumedFile` adapter exposing the same `.name`, `.size`, `.getvalue()` shape).
- `list_papers()` and `list_paper_files(thread_id)` — return list[dict], consumed as dict rows with `row["status"]`, `row["topic"]`, `row["file_name"]`, etc. in both the page code and the integration test.
- `get_checkpointer()` — module-level singleton, used identically in `app.py` and `pages/1_New_Paper.py`.
