# Paper History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-mode "Past papers" history block to the chat-page sidebar and a delete button to each row of the landing-page "My papers" list, with `agent/db.py:delete_paper` extended to also clean up orphan LangGraph checkpoint rows.

**Architecture:** Two thin UI additions over the existing Supabase persistence layer. No schema changes, no new env vars, no new files. The sidebar block calls `db.list_papers()`, filters by `st.session_state.mode`, and reuses the existing `resume_paper_id`-driven resume flow. The delete column on the landing page calls the extended `delete_paper`, which now also deletes from `checkpoint_writes` → `checkpoint_blobs` → `checkpoints` filtered by `thread_id` (via the existing `supabase-py` client).

**Tech Stack:** Python, Streamlit, `supabase-py`, pytest with `unittest.mock`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-20-paper-history-design.md`

---

## Phases

1. **Db extension (TDD)** — extend `delete_paper` to wipe LangGraph checkpoint rows (Task 1).
2. **Landing-page delete UI** — add the trash-icon column (Task 2).
3. **Chat-page sidebar history** — add the per-mode past-papers block (Task 3).
4. **Manual smoke verification** (Task 4).

Each task is one focused commit. No file is touched by more than one task.

## File touch list

- Modify: `agent/db.py` — extend `delete_paper`.
- Modify: `tests/test_db.py` — extend the existing delete-cascade test.
- Modify: `app.py` — split each "My papers" row into a `[9, 1]` two-column layout (resume + delete).
- Modify: `pages/1_New_Paper.py` — insert the "📂 Past papers" sidebar block between "← Back to dashboard" and "📄 Readings / data".

No new files. No migrations. No env changes.

---

## Phase 1 — Db extension (TDD)

### Task 1: Extend `delete_paper` to wipe LangGraph checkpoint rows

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\tests\test_db.py:136-156` (existing `test_delete_paper_cascades_to_files_and_storage`)
- Modify: `C:\Users\amine\Desktop\ProjetAI\agent\db.py:83-93` (existing `delete_paper` function)

**Background:** Today's `delete_paper` cleans `papers` (cascading `paper_files` via FK), the Storage bucket, but NOT LangGraph's `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` tables. Those rows are keyed by `thread_id` (which equals `papers.id`) but have no FK to `papers`, so they accumulate as orphans. We saw this during the 2026-05-20 manual cleanup, which had to truncate them by hand. The extension uses the same `supabase-py` client — these LangGraph tables live in `public` and are exposed by PostgREST. Delete order: `checkpoint_writes` → `checkpoint_blobs` → `checkpoints` (leaf to root by likely FK direction; if real FKs disagree at runtime the integration test will surface it).

- [ ] **Step 1: Extend the existing failing test**

Open `C:\Users\amine\Desktop\ProjetAI\tests\test_db.py`. Find `test_delete_paper_cascades_to_files_and_storage` (currently around lines 136–156). Replace the entire function with:

```python
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
    delete.return_value.eq.assert_any_call("id", "abc-123")

    # Wipe LangGraph orphan checkpoint rows (writes → blobs → checkpoints).
    client.table.assert_any_call("checkpoint_writes")
    client.table.assert_any_call("checkpoint_blobs")
    client.table.assert_any_call("checkpoints")
    # All three checkpoint deletes filter by thread_id (papers delete used id).
    delete.return_value.eq.assert_any_call("thread_id", "abc-123")
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `.venv/Scripts/python -m pytest tests/test_db.py::test_delete_paper_cascades_to_files_and_storage -v`

Expected: FAIL. The new assertion `client.table.assert_any_call("checkpoint_writes")` raises `AssertionError: table('checkpoint_writes') call not found.`

- [ ] **Step 3: Extend `delete_paper` in `agent/db.py`**

Open `C:\Users\amine\Desktop\ProjetAI\agent\db.py`. Find the existing `delete_paper` function (currently around lines 83–93):

```python
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

Replace with:

```python
def delete_paper(thread_id: str) -> None:
    """Delete a paper, its files (metadata + Storage), and LangGraph checkpoints.

    Cleans, in order:
      1. Storage blobs listed in paper_files for this thread.
      2. LangGraph orphan rows in checkpoint_writes / checkpoint_blobs / checkpoints
         (no FK to papers, must be cleaned separately).
      3. The papers row (paper_files rows cascade via FK ON DELETE CASCADE).
    """
    client = get_client()
    files = (client.table(_FILES_TABLE)
             .select("storage_path")
             .eq("paper_id", thread_id)
             .execute())
    paths = [row["storage_path"] for row in (files.data or [])]
    if paths:
        client.storage.from_(_BUCKET).remove(paths)
    # LangGraph checkpoint tables — same Postgres DB, no FK to papers, so we
    # wipe them through the SDK. Order: writes → blobs → checkpoints.
    for tbl in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        client.table(tbl).delete().eq("thread_id", thread_id).execute()
    client.table(_PAPERS_TABLE).delete().eq("id", thread_id).execute()
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `.venv/Scripts/python -m pytest tests/test_db.py::test_delete_paper_cascades_to_files_and_storage -v`

Expected: PASS, 1 test passed.

- [ ] **Step 5: Run the full unit suite to confirm no regression**

Run: `.venv/Scripts/python -m pytest --ignore=tests/integration -q`

Expected: previously-passing tests still pass — 52 passed, 1 skipped (the golden snapshot).

- [ ] **Step 6: Commit**

```bash
git add agent/db.py tests/test_db.py
git commit -m "$(cat <<'EOF'
feat(db): delete_paper also wipes LangGraph checkpoint rows

The papers table is the only one that cascade-deletes paper_files.
LangGraph's checkpoints / checkpoint_blobs / checkpoint_writes have no
FK to papers and were left as orphans after delete_paper, accumulating
forever. Wipe them through the same supabase-py client.

Order: writes -> blobs -> checkpoints.
EOF
)"
```

---

## Phase 2 — Landing-page delete UI

### Task 2: Add a delete column to "My papers"

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\app.py:142-157` (the "My papers" rendering block)

**No new tests.** This is a pure UI change; behavior is validated manually in Task 4.

- [ ] **Step 1: Locate the existing block**

Open `C:\Users\amine\Desktop\ProjetAI\app.py`. Find the "My papers" section (currently around lines 142–157). The current code is:

```python
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
```

- [ ] **Step 2: Replace with the two-column row**

Replace the block above with:

```python
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
        col_label, col_del = st.columns([9, 1])
        if col_label.button(label, key=f"resume_{row['id']}", use_container_width=True):
            st.session_state.resume_paper_id = row["id"]
            st.switch_page("pages/1_New_Paper.py")
        if col_del.button("🗑️", key=f"del_{row['id']}", help="Delete this paper", use_container_width=True):
            try:
                db.delete_paper(row["id"])
            except Exception as e:
                st.error(f"Could not delete: {e}")
            else:
                st.rerun()
```

Key things to verify:
- `[9, 1]` column ratio keeps the resume label dominant.
- Resume button key stays `resume_{id}` (unchanged so any session state targeting it still works).
- Delete button key is `del_{id}` (distinct namespace, no collision).
- Delete failure shows a non-fatal error; success triggers `st.rerun()` so the list refreshes.

- [ ] **Step 3: Run the unit suite to confirm no regression**

Run: `.venv/Scripts/python -m pytest --ignore=tests/integration -q`

Expected: 52 passed, 1 skipped. The page isn't exercised by unit tests — this just confirms nothing imports broke.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
feat(ui): add delete button to landing-page 'My papers' list

Two-column row: resume label (9 wide) | trash icon (1 wide). Click
delete -> db.delete_paper(id) -> st.rerun(). No confirmation dialog;
recovery requires the Supabase dashboard, same as before.
EOF
)"
```

---

## Phase 3 — Chat-page sidebar history

### Task 3: Add the per-mode "Past papers" sidebar block

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py` — the sidebar section (currently around lines 56–73)

**No new tests.** Manually validated in Task 4.

- [ ] **Step 1: Locate the insertion point in the sidebar**

Open `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py`. Find the sidebar block. After the recent edits the relevant lines are roughly:

```python
    if st.button("← Back to dashboard", use_container_width=True):
        st.switch_page("app.py")

    st.divider()
    st.markdown("### 📄 Readings / data")
```

The new "Past papers" block goes **between** the existing `st.divider()` and the `### 📄 Readings / data` heading.

- [ ] **Step 2: Insert the past-papers block**

Replace the snippet above with:

```python
    if st.button("← Back to dashboard", use_container_width=True):
        st.switch_page("app.py")

    st.divider()
    st.markdown("### 📂 Past papers")
    try:
        _all_papers = db.list_papers()
    except Exception as e:
        st.caption(f"Could not load history: {e}")
        _all_papers = []
    _same_mode = [p for p in _all_papers if p["mode"] == st.session_state.mode]
    if not _same_mode:
        st.caption("No past papers yet.")
    else:
        for p in _same_mode:
            _icon = "✅" if p["status"] == "complete" else "✏️"
            _label = f"{_icon} {p['topic'][:40]}  ·  {p['updated_at'][:10]}"
            if st.button(_label, key=f"sb_resume_{p['id']}", use_container_width=True):
                st.session_state.resume_paper_id = p["id"]
                st.rerun()

    st.divider()
    st.markdown("### 📄 Readings / data")
```

Key things to verify:
- `_all_papers`, `_same_mode`, `_icon`, `_label` use underscore prefixes to signal "local-to-block" and avoid colliding with any other names in the page.
- Topic is truncated to 40 chars so the date column stays visible in narrow sidebars.
- Button key prefix `sb_resume_` (sidebar-resume) is distinct from the landing-page `resume_` keys — Streamlit raises if duplicates exist across reruns and these pages share session state.
- On click: sets `st.session_state.resume_paper_id` and calls `st.rerun()`. The existing resume block at `pages/1_New_Paper.py:225` handles the rest — no page switch needed since we're already on the chat page.
- Empty state is the generic `"No past papers yet."` (spec choice — avoids awkward emoji pluralization).

- [ ] **Step 3: Run the unit suite to confirm no regression**

Run: `.venv/Scripts/python -m pytest --ignore=tests/integration -q`

Expected: 52 passed, 1 skipped.

- [ ] **Step 4: Commit**

```bash
git add pages/1_New_Paper.py
git commit -m "$(cat <<'EOF'
feat(ui): per-mode 'Past papers' history in chat-page sidebar

Lists papers of the current mode, sorted most-recent-first.
Click -> resume_paper_id + st.rerun() -> existing resume block
re-downloads files and syncs checkpoint. No new resume logic.
EOF
)"
```

---

## Phase 4 — Manual smoke verification

### Task 4: End-to-end browser verification

**Files:** none — verification only.

This exercises both new pieces against a live Supabase project. Assumes the same `.env` from the persistence smoke is in place.

- [ ] **Step 1: Start Streamlit**

If Streamlit isn't already running, in a separate terminal: `streamlit run app.py`. Open http://localhost:8501.

- [ ] **Step 2: Set up some history**

Create three short papers (don't need to finish them — `(untitled)` is fine for this test):
- Click **Literature Review** → type "Test survey 1" → wait for outline checkpoint → back to dashboard.
- Click **Empirical Paper** → type "Test empirical 1" → wait for outline checkpoint → back to dashboard.
- Click **Term Paper** → type "Test term 1" → wait for outline checkpoint → back to dashboard.

Verify on the landing page: "My papers" lists three rows, one per mode, each with status ✏️ (in-progress) and a 🗑️ icon on the right.

- [ ] **Step 3: Verify per-mode sidebar filter**

- Click the **Literature Review** card → the chat-page sidebar's "📂 Past papers" should list **only "Test survey 1"** (and possibly the freshly-created untitled row for this click — that's expected and out of scope).
- Click "← Back to dashboard" → click the **Term Paper** card → sidebar's "📂 Past papers" should list **only "Test term 1"** (and the new untitled). The survey paper should not appear.

- [ ] **Step 4: Verify resume-from-sidebar**

Inside the Term Paper page, click the "Test term 1" entry in the sidebar history. The main panel should switch to that paper's checkpoint card (outline approval). The page does not reload; resume is in-place.

- [ ] **Step 5: Verify delete + checkpoint cleanup**

Back to dashboard. Count `checkpoints` rows before:

```
.venv/Scripts/python -c "from dotenv import load_dotenv; load_dotenv(); import os, psycopg; url=os.getenv('SUPABASE_DB_URL'); conn=psycopg.connect(url+('&' if '?' in url else '?')+'connect_timeout=10'); cur=conn.cursor(); cur.execute('select count(*) from checkpoints'); print('checkpoints before:', cur.fetchone()[0]); conn.close()"
```

Note the count. In the "My papers" list, click 🗑️ next to "Test survey 1". The row should disappear. Run the same count command — the number should drop by however many checkpoint rows that one paper had (typically 5–15).

Repeat for the other two test papers if you want a clean DB.

- [ ] **Step 6: Verify empty state**

After deleting all test papers, the chat-page sidebar should show `"No past papers yet."` under "📂 Past papers" for whichever mode you visit.

- [ ] **Step 7: Stop Streamlit**

Ctrl+C in the terminal running it.

---

## Self-Review (already applied)

**Spec coverage:**
- Goal #1 (per-mode sidebar history) → Task 3.
- Goal #2 (delete button + ghost cleanup) → Task 2 (button) + Task 1 (extended delete).
- Component 1 (sidebar block, insertion point, click → resume_paper_id → rerun) → Task 3.
- Component 2 UI (`[9, 1]` columns, trash icon, no confirmation) → Task 2.
- Component 2 db extension (checkpoint cleanup, dependency order) → Task 1.
- Data flow (sidebar click and delete click) → wired exactly as specced in Tasks 2 + 3.
- Error handling rows in spec (list_papers fail, delete fail, individual checkpoint failures) → Task 3 sidebar try/except, Task 2 delete try/except, Task 1 leaves checkpoint failures uncaught so partial deletes surface as errors. All three behaviors implemented.
- Tests in spec (extend `test_delete_paper_cascades_to_files_and_storage`) → Task 1 Step 1.
- File touch list (4 files) → Tasks 1–3 hit exactly those four files.
- Out of scope (untitled ghost row at create time) → unchanged by this plan.

**Placeholder scan:** No TBD/TODO/"similar to". Every step has concrete code or commands.

**Type/signature consistency:**
- `db.delete_paper(thread_id)` — same signature before and after Task 1; call sites in Task 2 unchanged.
- `db.list_papers()` returns `list[dict]` — consumed identically in `app.py` (Task 2) and `pages/1_New_Paper.py` (Task 3): `row["status"]`, `row["topic"]`, `row["mode"]`, `row["updated_at"]`, `row["id"]`.
- Streamlit button key conventions: landing page uses `resume_{id}` and `del_{id}`; sidebar uses `sb_resume_{id}`. All three are distinct namespaces — no duplicate-key collisions across the page or between landing and chat page.
- `st.session_state.resume_paper_id` is the single resume trigger; both Task 2 (landing) and Task 3 (sidebar) set it; the existing resume block at `pages/1_New_Paper.py:225` consumes it. No new resume code in either task.
