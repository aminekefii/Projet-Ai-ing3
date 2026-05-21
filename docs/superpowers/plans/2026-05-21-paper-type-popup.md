# Reference-File Popup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the user picks a paper type, block the chat input behind an `@st.dialog` modal that asks Survey/Term users whether they have a reference file and forces Empirical users to upload data up-front.

**Architecture:** One new pure helper module (`agent/ui_helpers.py`) with a single function and a unit test. All UI work lives in `pages/1_New_Paper.py`: add a `file_choice` session-state flag, a `@st.dialog` function, a gate that calls the dialog when the flag is `None`, conditional sidebar uploader, and resume-path logic that derives the flag from `db.list_paper_files`. One line in `app.py` resets the flag when a mode card is clicked. No agent/graph changes, no DB schema changes.

**Tech Stack:** Python 3, Streamlit ≥1.40 (`@st.dialog`), Supabase (existing `db.py` helpers), pytest.

**Spec:** `docs/superpowers/specs/2026-05-21-paper-type-popup-design.md`

---

## File map

| Path | Action | Responsibility |
|---|---|---|
| `agent/ui_helpers.py` | Create | Pure functions for dialog routing (testable without Streamlit). |
| `tests/test_ui_helpers.py` | Create | Unit tests for the helper. |
| `pages/1_New_Paper.py` | Modify | Add `file_choice` to defaults, define dialog, add gate, conditional sidebar, resume logic. |
| `app.py` | Modify | Add `file_choice` to defaults; reset to `None` on mode-card click. |

---

### Task 1: Pure helper module + unit test

The dialog has one branching question — *for this mode, what step should the dialog start at?* Empirical jumps straight to upload; everything else starts at the Yes/No question. Extract that as a pure function so it can be unit-tested without importing Streamlit.

**Files:**
- Create: `agent/ui_helpers.py`
- Create: `tests/test_ui_helpers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ui_helpers.py`:

```python
"""Unit tests for pure UI helpers (no Streamlit imports)."""
from agent.ui_helpers import initial_dialog_step


def test_empirical_starts_at_upload():
    assert initial_dialog_step("empirical") == "upload"


def test_survey_starts_at_ask():
    assert initial_dialog_step("survey") == "ask"


def test_term_starts_at_ask():
    assert initial_dialog_step("term") == "ask"


def test_unknown_mode_falls_back_to_ask():
    # Defensive: any future mode that isn't 'empirical' should show the Yes/No first.
    assert initial_dialog_step("future-mode") == "ask"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```
pytest tests/test_ui_helpers.py -v
```
Expected: 4 errors with `ModuleNotFoundError: No module named 'agent.ui_helpers'`.

- [ ] **Step 3: Create the helper module**

Create `agent/ui_helpers.py`:

```python
"""Pure helpers for the New Paper page UI.

Kept separate from the page module so they can be unit-tested without
importing Streamlit (which pulls in a lot and is awkward to fake).
"""


def initial_dialog_step(mode: str) -> str:
    """Return the initial step name for the reference-file dialog.

    Empirical papers go straight to the upload step (a data file is required).
    All other modes (survey, term, anything new) start at the Yes/No question.
    """
    return "upload" if mode == "empirical" else "ask"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```
pytest tests/test_ui_helpers.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add agent/ui_helpers.py tests/test_ui_helpers.py
git commit -m "feat(ui): add initial_dialog_step helper for paper-type popup"
```

---

### Task 2: Add `file_choice` to session-state defaults

Add the gate flag to both `defaults` dicts (one on the dashboard, one on the New Paper page) and reset it explicitly in the dashboard's mode-card click handler. The New Paper page's "New chat" button already iterates `defaults` so it will reset the flag for free.

This task introduces the flag without any behavior change — nothing reads it yet, so the app still runs as before.

**Files:**
- Modify: `app.py:15-24`, `app.py:131-143`
- Modify: `pages/1_New_Paper.py:19-28`

- [ ] **Step 1: Add `file_choice` to `app.py` defaults**

In `app.py`, change the `defaults` block to:

```python
defaults = {
    "thread_id": str(uuid.uuid4()),
    "checkpointer": None,
    "vectorstore": None,
    "indexed_files": [],
    "mode": "survey",
    "pending_checkpoint": None,
    "run_started": False,
    "trace": [],
    "file_choice": None,
}
```

- [ ] **Step 2: Reset `file_choice` in the mode-card click handler**

In `app.py`, inside the `if st.button(f"Start →", ...)` block, after the existing `st.session_state.trace = []` line and before `st.switch_page(...)`, add:

```python
st.session_state.file_choice = None
```

The block should end up looking like:

```python
st.session_state.mode = mode["key"]
st.session_state.thread_id = new_id
st.session_state.checkpointer = get_checkpointer()
st.session_state.pending_checkpoint = None
st.session_state.run_started = False
st.session_state.trace = []
st.session_state.file_choice = None
st.switch_page("pages/1_New_Paper.py")
```

- [ ] **Step 3: Add `file_choice` to `pages/1_New_Paper.py` defaults**

In `pages/1_New_Paper.py`, change the `defaults` block to:

```python
defaults = {
    "thread_id": str(uuid.uuid4()),
    "checkpointer": None,
    "vectorstore": None,
    "indexed_files": [],
    "mode": "survey",
    "pending_checkpoint": None,
    "run_started": False,
    "trace": [],
    "file_choice": None,
}
```

- [ ] **Step 4: Run the existing test suite to confirm nothing broke**

Run:
```
pytest -q
```
Expected: all tests pass (no new tests, no regressions — this change touches Streamlit-only code).

- [ ] **Step 5: Commit**

```
git add app.py pages/1_New_Paper.py
git commit -m "feat(state): add file_choice flag to session defaults"
```

---

### Task 3: Define the `@st.dialog` function

Add the modal function to `pages/1_New_Paper.py`. It is defined but not yet called by the gate — the app's behavior is still unchanged after this commit, but the dialog is ready to wire up in Task 4.

The dialog uses one extra session-state key, `dialog_step`, to switch between the Yes/No view and the upload view. The key is created lazily inside the dialog and popped when the dialog closes successfully.

**Files:**
- Modify: `pages/1_New_Paper.py` (insert function definition; placement: after the `MODE_LABELS` dict, before the `# Hide Streamlit's auto-generated multipage nav` line — i.e. around line 45)

- [ ] **Step 1: Add the dialog function**

In `pages/1_New_Paper.py`, immediately after the `MODE_LABELS = {...}` dict (around line 44), insert:

```python
@st.dialog("Reference material", width="large")
def file_choice_dialog():
    """Gate the chat input on whether the user has a reference file.

    Survey/Term: Yes/No → optional upload. Empirical: upload-required.
    On commit, sets st.session_state.file_choice to "yes" or "no" and pops
    dialog_step so the gate stops re-opening the modal.
    """
    from agent.ui_helpers import initial_dialog_step

    if "dialog_step" not in st.session_state:
        st.session_state.dialog_step = initial_dialog_step(st.session_state.mode)

    if st.session_state.dialog_step == "ask":
        st.markdown("**Do you have a file you'd like to use as a reference?**")
        st.caption("PDFs, TXT, or CSV are supported. You can also add files later from the sidebar.")
        c1, c2 = st.columns(2)
        if c1.button("✅ Yes, I have a file", use_container_width=True, type="primary"):
            st.session_state.dialog_step = "upload"
            st.rerun()
        if c2.button("💬 No, start chat directly", use_container_width=True):
            st.session_state.file_choice = "no"
            st.session_state.pop("dialog_step", None)
            st.rerun()
        st.divider()
        if st.button("← Cancel and pick a different mode", key="dialog_cancel_ask"):
            try:
                db.delete_paper(st.session_state.thread_id)
            except Exception:
                pass
            st.session_state.pop("dialog_step", None)
            st.session_state.file_choice = None
            st.switch_page("app.py")

    elif st.session_state.dialog_step == "upload":
        if st.session_state.mode == "empirical":
            st.markdown("**Upload your data file.**")
            st.caption("Empirical papers are built around your own data — please upload a CSV, PDF, or TXT to continue.")
        else:
            st.markdown("**Upload your reference file(s).**")
            st.caption("PDFs, TXT, or CSV are supported.")

        uploaded = st.file_uploader(
            "Files",
            type=["pdf", "txt", "csv"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="dialog_uploader",
        )
        index_disabled = not uploaded
        if st.session_state.mode == "empirical":
            col_idx, = st.columns(1)
            col_back = None
        else:
            col_idx, col_back = st.columns([3, 1])

        if col_idx.button(
            "📚 Index",
            use_container_width=True,
            type="primary",
            disabled=index_disabled,
            key="dialog_index",
        ):
            from agent.rag import index_uploaded_files
            with st.spinner("Indexing…"):
                vs, summary = index_uploaded_files(uploaded)
            if vs is None:
                st.warning("No usable text extracted — try a different file.")
            else:
                st.session_state.vectorstore = vs
                st.session_state.indexed_files = summary
                for f in uploaded:
                    try:
                        db.upload_file(st.session_state.thread_id, f)
                    except Exception as e:
                        st.warning(f"Could not save '{f.name}' to Storage: {e}")
                st.session_state.file_choice = "yes"
                st.session_state.pop("dialog_step", None)
                st.rerun()

        if col_back is not None:
            if col_back.button("← Back", use_container_width=True, key="dialog_back"):
                st.session_state.dialog_step = "ask"
                st.rerun()

        if st.session_state.mode == "empirical":
            st.divider()
            if st.button("← Cancel and pick a different mode", key="dialog_cancel_upload"):
                try:
                    db.delete_paper(st.session_state.thread_id)
                except Exception:
                    pass
                st.session_state.pop("dialog_step", None)
                st.session_state.file_choice = None
                st.switch_page("app.py")
```

- [ ] **Step 2: Run the app to make sure nothing crashed at import time**

Run:
```
streamlit run app.py
```
Expected: dashboard loads. Click "Start →" on any card — the New Paper page loads as it did before (the dialog isn't wired up yet, so behavior is identical).

Stop the app with Ctrl+C.

- [ ] **Step 3: Commit**

```
git add pages/1_New_Paper.py
git commit -m "feat(ui): add @st.dialog function for reference-file choice"
```

---

### Task 4: Wire up the gate

Add the gate that calls `file_choice_dialog()` when `st.session_state.file_choice` is `None`. This is the commit where the UX actually changes: clicking "Start →" now opens the modal before the chat input renders.

**Files:**
- Modify: `pages/1_New_Paper.py` (insert gate immediately before `render_trace()` — i.e. immediately before the `# --- Main flow ---` block around line 408)

- [ ] **Step 1: Add the gate**

In `pages/1_New_Paper.py`, find this block at the bottom of the file (around line 408):

```python
# --- Main flow ---
render_trace()
```

Insert the gate immediately before it:

```python
# --- Reference-file gate ---
# Block the chat input until the user commits to a Yes/No choice (or, for
# empirical mode, has uploaded data). Resume sets file_choice up-front.
if not st.session_state.run_started and st.session_state.file_choice is None:
    file_choice_dialog()
    st.stop()


# --- Main flow ---
render_trace()
```

- [ ] **Step 2: Manually verify the gate fires (Survey "No" path)**

Run:
```
streamlit run app.py
```

- Click "Start →" on **Literature Review**.
- Expected: a modal opens with the Yes/No question.
- Click "💬 No, start chat directly."
- Expected: modal closes, chat input is visible at the bottom of the page.
- Type a topic like `test` and submit.
- Expected: the outline-generating spinner appears (you can stop the run after this — we're only checking the gate works).

Stop the app with Ctrl+C.

- [ ] **Step 3: Manually verify the gate fires (Empirical upload path)**

Run:
```
streamlit run app.py
```

- Click "Start →" on **Empirical Paper**.
- Expected: a modal opens directly in upload form (no Yes/No buttons), with "Upload your data file." copy.
- Expected: the "📚 Index" button is disabled.
- Drop in a small PDF or TXT file from anywhere on disk.
- Expected: the "📚 Index" button becomes enabled.
- Click "📚 Index."
- Expected: modal closes, chat input is visible, sidebar shows the indexed file under "📂 Readings / data."

Stop the app with Ctrl+C.

- [ ] **Step 4: Commit**

```
git add pages/1_New_Paper.py
git commit -m "feat(ui): gate New Paper chat input behind file-choice modal"
```

---

### Task 5: Hide the sidebar uploader when the user picked "No"

After the user commits to "No" for this paper, the sidebar uploader should be hidden — the choice is committed for this paper per the design. For "Yes," the sidebar uploader stays visible so the user can add more files later. Empirical always shows it.

**Files:**
- Modify: `pages/1_New_Paper.py:101-131` (wrap the existing sidebar uploader block in a conditional)

- [ ] **Step 1: Wrap the sidebar uploader in a conditional**

In `pages/1_New_Paper.py`, find this block (around line 100):

```python
    st.divider()
    st.markdown("### 📄 Readings / data")
    uploaded = st.file_uploader(
        "Upload PDF or TXT (CSV for empirical mode)",
        type=["pdf", "txt", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
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

    if st.session_state.indexed_files:
        for name, n in st.session_state.indexed_files:
            st.caption(f"• `{name}` — {n} chunks")
```

Replace it with this version (the whole block including the "indexed files" preview is wrapped, so when hidden nothing readings-related shows):

```python
    if st.session_state.file_choice != "no":
        st.divider()
        st.markdown("### 📄 Readings / data")
        uploaded = st.file_uploader(
            "Upload PDF or TXT (CSV for empirical mode)",
            type=["pdf", "txt", "csv"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
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

        if st.session_state.indexed_files:
            for name, n in st.session_state.indexed_files:
                st.caption(f"• `{name}` — {n} chunks")
```

- [ ] **Step 2: Manually verify "No" path hides the sidebar uploader**

Run:
```
streamlit run app.py
```

- Click "Start →" on **Literature Review**.
- Click "💬 No, start chat directly."
- Expected: the modal closes. In the sidebar, the "📄 Readings / data" section is **not** present.
- Click "← Back to dashboard" in the sidebar.
- Expected: dashboard shows. No orphan paper in "My papers" (well, there will be one in "(untitled)" state — that's expected; it'll get cleaned up only via the Cancel link inside the modal).

- [ ] **Step 3: Manually verify "Yes" path keeps the sidebar uploader**

- From the dashboard, click "Start →" on **Literature Review** again.
- Click "✅ Yes, I have a file."
- Upload a small PDF or TXT in the modal, click "📚 Index."
- Expected: modal closes; in the sidebar, the "📄 Readings / data" section **is** visible and shows the indexed file.

Stop the app with Ctrl+C.

- [ ] **Step 4: Commit**

```
git add pages/1_New_Paper.py
git commit -m "feat(ui): hide sidebar uploader after No file-choice"
```

---

### Task 6: Resume path derives `file_choice`

When the user resumes a paper from the dashboard's "My papers" list, the modal must not re-open. The resume block already calls `db.list_paper_files(resume_id)` to re-download persisted files; we use that same result to set `file_choice` before the gate runs.

**Files:**
- Modify: `pages/1_New_Paper.py:367-396` (the `file_rows = db.list_paper_files(...)` block inside the resume branch)

- [ ] **Step 1: Set `file_choice` from `file_rows`**

In `pages/1_New_Paper.py`, find this line inside the resume block (around line 367):

```python
    # Re-download persisted files and rebuild FAISS in-memory.
    file_rows = db.list_paper_files(resume_id)
    if file_rows:
        from agent.rag import index_uploaded_files
```

Insert one line immediately after `file_rows = db.list_paper_files(resume_id)`:

```python
    # Re-download persisted files and rebuild FAISS in-memory.
    file_rows = db.list_paper_files(resume_id)
    st.session_state.file_choice = "yes" if file_rows else "no"
    if file_rows:
        from agent.rag import index_uploaded_files
```

- [ ] **Step 2: Manually verify resume of a "Yes" paper skips the modal**

Run:
```
streamlit run app.py
```

- From the dashboard's "My papers" list, click a paper that was created earlier with files (from Task 4 step 3 or Task 5 step 3).
- Expected: no modal appears. The New Paper page renders directly, with the sidebar showing the re-indexed file.

- [ ] **Step 3: Manually verify resume of a "No" paper skips the modal**

- Back to dashboard. Click a paper that was created earlier without files (from Task 4 step 2 or Task 5 step 2).
- Expected: no modal appears. The New Paper page renders directly. Sidebar has **no** "📄 Readings / data" section.

Stop the app with Ctrl+C.

- [ ] **Step 4: Commit**

```
git add pages/1_New_Paper.py
git commit -m "feat(ui): derive file_choice from persisted files on resume"
```

---

### Task 7: Full manual verification matrix

Run the full test matrix from the spec to catch anything the per-task checks missed. This is a checkpoint — if anything in this list fails, fix it before declaring done.

**Files:** none modified — verification only.

- [ ] **Step 1: Run the app and walk through every row in this matrix**

Run:
```
streamlit run app.py
```

Walk through, in order:

1. **Survey → No** — Start Literature Review → "No" → topic chat reachable → outline appears. Sidebar uploader hidden.
2. **Survey → Yes → Index** — Start Literature Review → "Yes" → upload PDF in modal → Index → modal closes → sidebar uploader visible with the indexed file. Topic chat reachable.
3. **Term → No** — Same shape as 1 on Term Paper.
4. **Term → Yes → Index** — Same shape as 2 on Term Paper.
5. **Empirical** — Start Empirical → modal opens directly in upload form, no "No" option → Index disabled until file chosen → modal closes after successful index → sidebar uploader visible.
6. **Modal dismissal (X / Esc)** — Click "Start →" on any mode → press Esc to close modal → click anywhere → modal re-opens. No path to the chat without committing.
7. **Cancel link inside modal (Ask step)** — Start Literature Review → click "← Cancel and pick a different mode" → dashboard shows → the just-created "(untitled)" row is **not** in "My papers."
8. **Cancel link inside modal (Empirical upload step)** — Start Empirical → click "← Cancel and pick a different mode" → dashboard shows → no orphan row.
9. **New chat button (sidebar)** — Finish a paper with "Yes" (or fake it: pick Yes, upload, then click "← Back to dashboard") → re-enter via dashboard → from the sidebar of the New Paper page click "➕ New chat" → modal re-appears.
10. **Resume "Yes" paper** — From "My papers," click a paper that has files → no modal → vectorstore re-indexed → sidebar uploader visible.
11. **Resume "No" paper** — From "My papers," click a paper that has no files → no modal → sidebar uploader hidden.
12. **Index failure** — Open the modal → upload an empty TXT file (e.g. create one with `New-Item -ItemType File empty.txt`) → click "📚 Index" → "No usable text extracted" warning shows inside the modal → modal stays open. (Streamlit may surface the warning on the next interaction; that's fine.)

For each, note pass/fail.

- [ ] **Step 2: Run the unit test suite once more to confirm no regressions**

Run:
```
pytest -q
```
Expected: all tests pass (including the new `test_ui_helpers.py`).

- [ ] **Step 3: If everything passed, no commit is needed — Task 7 is verification only**

If something failed, fix it, commit the fix, and re-run the failing row.

---

## After implementation

Per the brainstorming flow, once this plan completes, the next step is to merge `multi-agent` into `master` (or open a PR) — that's the user's call and outside this plan's scope.
