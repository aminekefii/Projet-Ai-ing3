# Paper History — Design

**Status**: approved
**Date**: 2026-05-20

## Goal

Make past papers easier to find and clean up:

1. While working in a paper mode (Literature Review, Empirical, Term), the sidebar shows the history of past papers **of that mode only** and resuming any of them takes one click.
2. The landing page's "My papers" list gets a delete button per row so the user can purge papers (including the `(untitled)` ghosts created by clicking a mode card and backing out).

## Non-goals

- Replaying the full chat trace of a past paper (every node's intermediate output). The current resume flow — show checkpoint state if mid-flow, show final output if complete — stays as-is.
- Restructuring when paper rows get created (currently created on mode-card click). The delete button is the chosen mitigation for `(untitled)` ghosts.
- Search / sort / pagination within the history list. The list is short by construction and shown most-recent-first via existing `list_papers` ordering.

## Architecture

Two small UI additions, one db-layer extension. No new tables, no new env vars.

```
Landing page (app.py)
   └── "My papers" row  ──►  [resume button | 🗑️ delete button]
                                                    └── db.delete_paper(id)  (extended)

Chat page (pages/1_New_Paper.py)
   └── Sidebar
        ├── "Start over" / "Back to dashboard"  (unchanged)
        ├── "📂 Past papers"  ◄── NEW
        │     └── list_papers() filtered by current mode
        │           → click → resume_paper_id → existing resume block
        └── "📄 Readings / data"  (unchanged)
```

## Component 1 — Per-mode sidebar history (chat page)

**File**: `pages/1_New_Paper.py`

A new block in the sidebar, inserted **between** the existing "← Back to dashboard" button and the "📄 Readings / data" file uploader.

**Behavior**:
- Reads `st.session_state.mode` to know the current paper type.
- Calls `db.list_papers()` (already sorted by `updated_at desc`) and filters to rows where `row["mode"] == current_mode`.
- Renders each match as a full-width `st.button`, label formatted: `{status_icon} {topic} · {updated_at[:10]}` — same conventions as the landing page list (✅ for complete, ✏️ for in-progress).
- Empty state: when no past papers of this mode exist, render `st.caption("No past papers yet.")`. (Generic phrasing — no awkward emoji-leading pluralization like "No past 📚 Literature Reviewss yet.")
- On click: set `st.session_state.resume_paper_id = row["id"]` and `st.rerun()`. The existing resume block at `pages/1_New_Paper.py:225` already handles the rest (downloads files, rebuilds FAISS, syncs checkpoint, persists complete state).

**Why this works without new resume logic**: the resume block is already entry-agnostic — it only cares that `resume_paper_id` is in session state. The landing-page button uses the same mechanism (just with a `st.switch_page` first). The sidebar entry skips the page switch because we're already on the chat page.

## Component 2 — Delete button on landing-page list

**Files**: `app.py`, `agent/db.py`

**UI change (`app.py`)**:
The current single-button row becomes a 2-column row:

```python
col_label, col_del = st.columns([9, 1])
if col_label.button(label, ...):  resume
if col_del.button("🗑️", key=f"del_{row['id']}", help="Delete this paper"):
    db.delete_paper(row["id"])
    st.rerun()
```

Width ratio `[9, 1]` keeps the resume label dominant. Trash icon stays compact. No confirmation dialog — Streamlit's reactive model makes those awkward, and the action is recoverable only via Supabase dashboard anyway, so we accept the same risk profile as the existing manual cleanup.

**db-layer change (`agent/db.py`)**:

Today's `delete_paper(thread_id)` removes:
- Storage blobs for that paper
- The `papers` row (and `paper_files` rows via FK `ON DELETE CASCADE`)

It does **not** touch LangGraph's three checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`). Those rows are keyed by `thread_id`, which equals `papers.id` in our setup, but there's no foreign key — they survive a paper delete and accumulate as orphans. We saw this in the 2026-05-20 smoke test cleanup, which had to truncate them manually.

Extend `delete_paper` to also delete those three tables filtered by `thread_id`, in dependency order: `checkpoint_writes` → `checkpoint_blobs` → `checkpoints`. Use the existing `supabase-py` client (these tables live in `public` and are exposed by PostgREST). One added block, three SDK calls.

## Data flow

**Sidebar click** (chat page):
```
user click → session_state.resume_paper_id = id → st.rerun()
  → existing resume block reads resume_paper_id
  → db.get_paper(id) → set mode, trace, run_started, _persisted_complete
  → db.list_paper_files(id) → db.download_file(...) → rebuild FAISS
  → build_graph() → get_state() → set pending_checkpoint
  → main panel renders accordingly
```

**Delete click** (landing page):
```
user click 🗑️ → db.delete_paper(id)
  → list paper_files rows → remove storage blobs
  → delete from checkpoint_writes/checkpoint_blobs/checkpoints WHERE thread_id=id
  → delete from papers WHERE id=id  (cascades paper_files)
  → st.rerun() → landing page re-renders without the row
```

## Error handling

- `db.list_papers()` fails in the sidebar: catch and show `st.caption("Could not load history: {err}")`. Don't crash the page — the user can still create a new paper.
- `db.delete_paper()` fails: catch in `app.py`, `st.error(f"Could not delete: {e}")`, no rerun. The row stays visible so the user can retry.
- LangGraph checkpoint deletes fail individually: the wrapping `delete_paper` already runs through them in sequence; any failure surfaces as an exception caught by the landing-page handler above. We do **not** swallow these — a partial delete leaves orphan rows and we want to know.

## Testing

- **Extend `tests/test_db.py::test_delete_paper_cascades_to_files_and_storage`**: add assertions that `client.table("checkpoint_writes").delete().eq("thread_id", "abc-123")`, then `checkpoint_blobs`, then `checkpoints` are called in that order. The existing storage + papers assertions stay.
- **Per-mode sidebar filter**: no unit test. It's a one-line list comprehension in page code; verified manually during the smoke test (Task 14 from the persistence work).
- **Smoke verification**: after implementing, on the chat page in Literature Review mode the sidebar should list only survey papers; switching modes should swap the list. Deleting from the landing page should remove the row and also wipe its checkpoint rows (verify by counting `checkpoints` in Supabase before/after).

## File touch list

- `pages/1_New_Paper.py` — add the sidebar history block.
- `app.py` — add delete column to "My papers" row.
- `agent/db.py` — extend `delete_paper` to wipe LangGraph checkpoint rows.
- `tests/test_db.py` — extend the delete-cascade test.

Four files. No new files, no migrations, no env changes.
