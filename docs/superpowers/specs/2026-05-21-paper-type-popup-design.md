# Reference-file popup after paper-type selection

**Date:** 2026-05-21
**Status:** Approved (design)
**Branch:** multi-agent

## Problem

After the user picks a paper type on the dashboard, the New Paper page goes straight to a chat input. The sidebar file uploader is easy to miss, so users routinely start writing without supplying any reference material — and uploaded files were sometimes assumed to be in use when they were only indexed for the document_search tool.

We need an explicit, blocking step that asks the user — once, right after they pick a mode — whether they have a reference file. The choice and the upload happen before they reach the chat input.

## Goals

- Make the "do you have a reference file?" decision an explicit, unmissable step.
- Block the chat input until the decision is committed.
- Force the user's data file to be supplied up-front for Empirical mode (where it is required by design).
- No DB schema changes; no changes to the agent graph.

## Non-goals

- Persisting the Yes/No choice as a separate column. The presence of `paper_files` rows is the source of truth on resume.
- Reworking how the graph consumes the vectorstore. Today's wiring stays.
- Adding automated UI tests for Streamlit page rendering.

## User flow

The dashboard (`app.py`) is unchanged — clicking "Start →" still creates the paper row and switches to the New Paper page.

On the New Paper page, before the chat input renders, a gate checks `st.session_state.file_choice`. If unset, a modal opens.

### Survey or Term mode

1. Modal opens with copy: *"Do you have a file you'd like to use as a reference?"* — two buttons:
   - **Yes, I have a file**
   - **No, start chat directly**
2. **Yes** → modal swaps to an *upload* view: file uploader + Index button. Index is disabled until at least one file is selected. Clicking Index runs the existing `index_uploaded_files` + `db.upload_file` logic. On success the modal closes and `file_choice = "yes"`. On indexing failure the modal stays open and shows the warning so the user can retry.
3. **No** → modal closes immediately, `file_choice = "no"`, and the sidebar uploader is hidden for the rest of this paper.

### Empirical mode

1. Modal opens directly in upload-required form with copy: *"Empirical papers are built around your own data — please upload a CSV / PDF / TXT to continue."*
2. No "No" option. Same indexing flow; modal closes only on successful index.

### Resumed papers

The resume block sets `file_choice` from `db.list_paper_files(resume_id)` — rows present ⇒ `"yes"`, empty ⇒ `"no"`. The gate sees a committed value and never opens the modal.

### Escape hatch

A small "← Cancel and pick a different mode" link inside the modal switches back to `app.py` and deletes the just-created paper row, so users who change their mind don't leave an orphaned row in "My papers."

## Components

Only `pages/1_New_Paper.py` changes structurally.

### Session-state additions

Add to the `defaults` dict:

- `file_choice`: `None | "yes" | "no"` — `None` means the gate must show.

No other new keys: `vectorstore` and `indexed_files` already exist in `defaults`.

### Dialog function

A single `@st.dialog("Reference material", width="large")` function. An internal `dialog_step` key drives a tiny state machine:

- `"ask"` — Yes/No buttons (Survey/Term only).
- `"upload"` — uploader + Index button (used by both modes; Empirical jumps straight here).

The dialog reads `st.session_state.mode` to decide which step to start at and what copy to show.

### Gate

Placed after the resume block and before `render_trace()`:

```python
if not st.session_state.run_started and st.session_state.file_choice is None:
    file_choice_dialog()
    st.stop()
```

`st.stop()` prevents the chat input from rendering until the choice is committed.

### Sidebar uploader, conditional

Wrap the existing `st.file_uploader` + Index block in `if st.session_state.file_choice != "no":`. After "No," the uploader stays hidden for the rest of this paper. After "Yes," it stays visible so the user can add more files later (indexing already supports adding to an existing vectorstore).

### Reset paths

- **New chat button (sidebar)** — the existing reset loop iterates `defaults`, so adding `file_choice` to `defaults` handles this for free.
- **Dashboard `Start →` button (`app.py`)** — set `st.session_state.file_choice = None` explicitly next to the other manual session writes, so the modal fires for the next paper.

### What does NOT change

- `app.py` — only the one `file_choice = None` line.
- `agent/` — graph, tools, state, prompts are all untouched.
- Supabase schema — no new columns or tables.
- The existing `index_uploaded_files` and `db.upload_file` calls are reused as-is from inside the modal.

## Data flow

### Inputs to the dialog

- `st.session_state.mode` — drives dialog shape.
- `st.session_state.thread_id` — used by `db.upload_file(thread_id, f)`.
- The user's file selections in the modal-local `st.file_uploader`.

### Outputs

| Path | `file_choice` | `vectorstore` | `indexed_files` | Supabase |
|---|---|---|---|---|
| Survey/Term → No | `"no"` | unchanged (None) | `[]` | nothing written |
| Survey/Term → Yes → Index OK | `"yes"` | FAISS store | summary list | rows in `paper_files` + blobs in Storage |
| Empirical → Index OK | `"yes"` | FAISS store | summary list | rows in `paper_files` + blobs in Storage |
| Any Index failure | unchanged (`None`) | unchanged | unchanged | nothing written; modal shows warning, stays open |

### Read path during the run — unchanged

`build_graph(...)` already takes `vectorstore=st.session_state.vectorstore`, and the topic-submission block already injects `user_data` only when `mode == "empirical"`. So:

- **No** path: `vectorstore=None`; the document_search tool degrades gracefully (it already handles None).
- **Yes** path: same wiring as today; the file is simply indexed in the modal rather than the sidebar.

### Resume path

Derives `file_choice` from `db.list_paper_files(resume_id)`: rows present ⇒ `"yes"`, empty ⇒ `"no"`. Set *before* the gate check, so the modal never re-opens on resume.

### New chat

The existing `for k, v in defaults.items(): st.session_state[k] = v` loop resets `file_choice` to `None` automatically once it's in `defaults`. Vectorstore and indexed_files are already in `defaults`, so they reset too.

## Edge cases

- **User dismisses the modal (X / Esc).** `file_choice` stays `None`. The next rerun hits the gate and re-opens the modal. No silent state — no path to the chat without a committed choice.
- **Indexing succeeds in-memory but Supabase upload fails.** Mirrors current behavior: vectorstore is set, storage failures surface as warnings, modal closes (file is usable this session). On the next resume the file just won't be there. Acceptable, matches today.
- **Empty file uploader on Empirical.** Index button stays disabled until at least one file is selected. No way past the gate without a file.
- **Cancel-and-switch-mode link.** Deletes the just-created paper row via `db.delete_paper(thread_id)` and `st.switch_page("app.py")`. Avoids orphan rows.

## Testing

UI-only change, so testing is manual. Run `streamlit run app.py` and walk through:

1. **Survey → No** — modal closes, sidebar uploader hidden, chat reachable, run completes.
2. **Survey → Yes → Index** — modal closes, sidebar uploader visible, document_search fires during research.
3. **Term → No** and **Term → Yes** — same as 1 and 2.
4. **Empirical** — modal opens directly in upload form with no "No" option; Index disabled until file chosen; modal closes only after successful index; `user_data` appears in graph state (visible in trace).
5. **Modal dismissal (X / Esc)** — close without choosing, click anywhere, modal re-opens.
6. **Cancel link inside modal** — switches back to dashboard, half-created paper row is deleted (no orphan in "My papers").
7. **New chat button (sidebar)** — after finishing one paper with "Yes," click New chat; modal re-appears.
8. **Resume "Yes" paper** — no modal, vectorstore re-indexed from Storage, sidebar uploader visible.
9. **Resume "No" paper** — no modal, sidebar uploader hidden.
10. **Index failure** — upload a corrupt/empty file in the modal; "No usable text extracted" warning shows inside the modal; modal stays open.

Automated tests: none added. Existing `tests/` suite doesn't cover Streamlit rendering and adding snapshot tests for this would be brittle.

## Out of scope

- Persisting `file_choice` as a column.
- Reworking how Survey/Term modes consume the vectorstore (e.g. injecting file content into `user_data` for non-Empirical modes). Separate decision.
- Re-styling the dashboard mode cards.
