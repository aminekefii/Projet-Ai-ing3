# Editable Checkpoint 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the read-only "Review draft" checkpoint with an editable layout: each section becomes a `st.text_area` with its reviewer issues shown inline, plus a title input pre-filled with the topic and an on-demand `✨ Suggest titles` button that calls the LLM.

**Architecture:** One additive `PaperState` field (`paper_title`), a one-line change in `finalize_node` (use `paper_title` with topic fallback), and a rewrite of the `cp == "finalize"` branch in `pages/1_New_Paper.py`. The title-suggestions LLM call is page-side, not a graph node. No new files, no schema changes, no new env vars.

**Tech Stack:** Python, Streamlit, LangGraph, langchain-openai, pytest.

**Spec:** `docs/superpowers/specs/2026-05-20-checkpoint3-editing-design.md`

---

## Phases

1. **Backend (TDD)** — `PaperState.paper_title`, `finalize_node` change, two new tests (Task 1).
2. **UI rewrite** — full replacement of the `cp == "finalize"` branch + session-state cleanup on resume/new-chat (Task 2).
3. **Manual smoke** (Task 3).

## File touch list

- Modify: `agent/state.py` — add `paper_title` to `PaperState`.
- Modify: `agent/nodes/finalize.py` — use `paper_title` with fallback.
- Modify: `tests/test_finalize.py` — two new tests (paper_title set; empty-string fallback).
- Modify: `pages/1_New_Paper.py` — rewrite `cp == "finalize"` branch; clear ephemeral UI keys in two other spots (resume block, New chat button).

No new files. No new dependencies (`ChatOpenAI` is already imported via `agent.graph`).

---

## Phase 1 — Backend (TDD)

### Task 1: `paper_title` in state + finalize node

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\tests\test_finalize.py` (append two tests)
- Modify: `C:\Users\amine\Desktop\ProjetAI\agent\state.py:60-62` (add field to `PaperState`)
- Modify: `C:\Users\amine\Desktop\ProjetAI\agent\nodes\finalize.py:39-43` (H1 line in `finalize_node`)

**Background:** Today `finalize_node` always uses `state["topic"]` as the paper's H1. We want users to override this at Checkpoint 3 via a new `paper_title` field. When the user leaves it blank (or never sets it), behavior is unchanged.

- [ ] **Step 1: Add the failing tests**

Open `C:\Users\amine\Desktop\ProjetAI\tests\test_finalize.py`. Append these two tests at the end of the file (after `test_finalize_orders_references_by_id_appearance`):

```python


def test_finalize_uses_paper_title_when_set(sample_state):
    """When paper_title is in state, it should replace topic as the H1."""
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "body", "Background": "more body"}
    sample_state["paper_title"] = "A Custom Paper Title"
    result = finalize_node(sample_state)
    first_line = result["final_output"].split("\n", 1)[0]
    assert first_line == "# A Custom Paper Title"


def test_finalize_falls_back_to_topic_when_paper_title_empty(sample_state):
    """Empty-string paper_title should fall back to topic, not produce '# '."""
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "body"}
    sample_state["paper_title"] = ""  # explicit empty
    result = finalize_node(sample_state)
    first_line = result["final_output"].split("\n", 1)[0]
    assert first_line == "# Transformer attention mechanisms"  # topic from fixture
```

The `sample_state` fixture in `tests/conftest.py` sets `topic="Transformer attention mechanisms"`, which is the expected fallback.

- [ ] **Step 2: Run the new tests, confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_finalize.py -v`

Expected: the two new tests FAIL. The first fails because `finalize_node` ignores `paper_title` and uses `topic`, so the H1 is `"# Transformer attention mechanisms"` instead of `"# A Custom Paper Title"`. The second test passes accidentally (topic is used regardless), but DON'T accept that — re-run it after the implementation to verify it's still green.

- [ ] **Step 3: Add `paper_title` to `PaperState`**

Open `C:\Users\amine\Desktop\ProjetAI\agent\state.py`. Find the existing `PaperState` TypedDict (around lines 48–62). The last two lines currently are:

```python
    forced_review_issues: list  # ReviewIssue[] — populated by drafter, consumed by reviewer
    analysis_results: dict  # {stat_name: value} — populated by data_analyzer
    tool_calls: list  # [{tool, input}, ...] — populated by researcher for UI trace
```

Add one line after `tool_calls`:

```python
    paper_title: str  # populated at Checkpoint 3; finalize falls back to topic when missing
```

The resulting tail of `PaperState`:

```python
    forced_review_issues: list  # ReviewIssue[] — populated by drafter, consumed by reviewer
    analysis_results: dict  # {stat_name: value} — populated by data_analyzer
    tool_calls: list  # [{tool, input}, ...] — populated by researcher for UI trace
    paper_title: str  # populated at Checkpoint 3; finalize falls back to topic when missing
```

`PaperState` already uses `total=False`, so all fields are optional — no migration concern.

- [ ] **Step 4: Update `finalize_node` to use `paper_title`**

Open `C:\Users\amine\Desktop\ProjetAI\agent\nodes\finalize.py`. Find the existing `finalize_node` function (around lines 23–44). The body is currently:

```python
def finalize_node(state: PaperState) -> dict:
    sections_md = "\n\n".join(
        f"## {section.title}\n\n{state['draft'].get(section.title, '')}"
        for section in state["outline"]
    )
    cited_ids_in_order: list[str] = []
    for section in state["outline"]:
        body = state["draft"].get(section.title, "")
        for cid in _CITATION_RE.findall(body):
            if cid not in cited_ids_in_order:
                cited_ids_in_order.append(cid)
    sources_by_id = {s.id: s for s in state["sources"]}
    refs_md = "\n".join(
        f"- **[{sid}]** {_format_reference(sources_by_id[sid])}"
        for sid in cited_ids_in_order if sid in sources_by_id
    )
    paper = (
        f"# {state['topic']}\n\n"
        f"{sections_md}\n\n"
        f"## References\n\n{refs_md}\n"
    )
    return {"final_output": paper}
```

Change ONLY the `paper = (...)` block. Replace:

```python
    paper = (
        f"# {state['topic']}\n\n"
        f"{sections_md}\n\n"
        f"## References\n\n{refs_md}\n"
    )
```

with:

```python
    title = state.get("paper_title") or state["topic"]
    paper = (
        f"# {title}\n\n"
        f"{sections_md}\n\n"
        f"## References\n\n{refs_md}\n"
    )
```

The `or` short-circuits when `paper_title` is missing OR is an empty string, falling back to `topic` in both cases.

- [ ] **Step 5: Run the new tests, confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_finalize.py -v`

Expected: PASS, 5 tests passed (the 3 original + 2 new).

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `.venv/Scripts/python -m pytest --ignore=tests/integration -q`

Expected: 54 passed, 1 skipped (previously 52 + 2 new tests).

- [ ] **Step 7: Commit**

```bash
git add agent/state.py agent/nodes/finalize.py tests/test_finalize.py
git commit -m "$(cat <<'EOF'
feat(state): paper_title field; finalize uses it with topic fallback

Adds an optional paper_title field to PaperState. finalize_node now
prefers state["paper_title"] for the H1, falling back to state["topic"]
when missing or empty. UI to set the field comes in the next commit.

Two new tests cover the set-explicitly path and the empty-string
fallback. Existing tests stay green (they don't set paper_title, so
the fallback branch is exercised).
EOF
)"
```

---

## Phase 2 — UI rewrite

### Task 2: Replace the Checkpoint 3 branch

**Files:**
- Modify: `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py` — three edit points:
  1. The `cp == "finalize"` branch inside `render_checkpoint_card` (currently around lines 255–270).
  2. The "➕ New chat" button handler (currently around lines 57–69) — clear ephemeral UI keys.
  3. The resume block (currently around lines 273–326) — clear ephemeral UI keys.

**No new automated tests.** The page is exercised manually in Task 3.

**Background:** This is the single substantive change. The new checkpoint must:
- Show a pre-filled title input with a `✨ Suggest titles` button that calls the LLM page-side.
- Render each section as a `st.text_area` with the section's reviewer issues shown above it (per-section, not globally).
- On Approve, push the edited title and edited section bodies into graph state via `graph.update_state` before running finalize.

Two ephemeral session-state keys are introduced (`title_input`, `title_suggestions`) and a sentinel (`pending_title`). These must be cleared when the user switches to a different paper (resume) or starts a new one ("➕ New chat"), or stale values will leak between papers.

- [ ] **Step 1: Replace the `cp == "finalize"` branch**

Open `C:\Users\amine\Desktop\ProjetAI\pages\1_New_Paper.py`. Find the existing block (around lines 255–270):

```python
    elif cp == "finalize":
        st.subheader("Checkpoint 3: Review draft")
        draft = snapshot.values.get("draft", {})
        review = snapshot.values.get("review")
        if review and review.issues:
            with st.expander(f"⚠️ Reviewer flagged {len(review.issues)} issue(s)"):
                for i in review.issues:
                    st.markdown(f"- **[{i.kind}]** {i.section}: {i.suggestion}")
        for title, body in draft.items():
            with st.expander(f"## {title}", expanded=False):
                st.markdown(body)
        if st.button("✅ Approve → finalize", type="primary", use_container_width=True):
            st.session_state.pending_checkpoint = None
            with st.spinner("Finalizing…"):
                stream_until_interrupt(None)
            st.rerun()
```

Replace the ENTIRE block (from `elif cp == "finalize":` through the closing `st.rerun()`) with:

```python
    elif cp == "finalize":
        st.subheader("Checkpoint 3: Review draft")

        # Drain any pending title suggestion before the text_input renders.
        # (Streamlit forbids writing to a widget's bound key after instantiation.)
        if "pending_title" in st.session_state:
            st.session_state.title_input = st.session_state.pop("pending_title")

        topic = snapshot.values.get("topic", "")
        outline = snapshot.values.get("outline", [])
        draft = snapshot.values.get("draft", {})
        review = snapshot.values.get("review")

        # ---- Title row ----
        st.markdown("### 📝 Paper title")
        if "title_input" not in st.session_state:
            st.session_state.title_input = snapshot.values.get("paper_title") or topic
        st.text_input("Title", key="title_input", label_visibility="collapsed")

        if st.button("✨ Suggest titles"):
            try:
                from langchain_openai import ChatOpenAI
                section_titles = [s.title for s in outline]
                prompt = (
                    f"Suggest 3 concise academic titles for a paper on the topic: {topic}\n"
                    f"The paper covers these sections: {', '.join(section_titles)}.\n"
                    f"Return one title per line. No numbering, no quotes, no commentary."
                )
                suggestion_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.7)
                response = suggestion_llm.invoke(prompt)
                suggestions = [
                    line.strip().strip('"').strip("'")
                    for line in response.content.split("\n") if line.strip()
                ][:5]
                st.session_state.title_suggestions = suggestions
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't generate suggestions: {e}")

        if st.session_state.get("title_suggestions"):
            st.caption("Suggestions (click to use):")
            for i, sugg in enumerate(st.session_state.title_suggestions):
                if st.button(sugg, key=f"sugg_{i}", use_container_width=True):
                    st.session_state.pending_title = sugg
                    st.rerun()

        st.divider()

        # ---- Editable sections ----
        st.markdown("### 📄 Sections")
        issues_by_section: dict[str, list] = {}
        if review and review.issues:
            for issue in review.issues:
                issues_by_section.setdefault(issue.section, []).append(issue)

        edited_bodies: dict[str, str] = {}
        for section in outline:
            section_issues = issues_by_section.get(section.title, [])
            if section_issues:
                with st.container(border=True):
                    st.markdown(f"⚠️ **Reviewer issues for {section.title}:**")
                    for issue in section_issues:
                        st.markdown(f"- **[{issue.kind}]** {issue.suggestion}")
            edited_bodies[section.title] = st.text_area(
                section.title,
                value=draft.get(section.title, ""),
                height=300,
                key=f"draft_{section.title}",
            )

        if st.button("✅ Approve → finalize", type="primary", use_container_width=True):
            graph.update_state(config(), {
                "draft": edited_bodies,
                "paper_title": st.session_state.title_input,
            })
            st.session_state.pending_checkpoint = None
            # Clear ephemeral UI keys so they don't leak to the next paper.
            st.session_state.pop("title_input", None)
            st.session_state.pop("title_suggestions", None)
            for section in outline:
                st.session_state.pop(f"draft_{section.title}", None)
            with st.spinner("Finalizing…"):
                stream_until_interrupt(None)
            st.rerun()
```

Key things to verify:
- The `if "pending_title" in st.session_state:` drain MUST run before `st.text_input(..., key="title_input", ...)` — otherwise Streamlit raises `StreamlitAPIException` when the suggestion click tries to update the widget value after instantiation.
- `label_visibility="collapsed"` hides the duplicate "Title" label since the section already has a markdown heading.
- `topic = snapshot.values.get("topic", "")` defends against the (rare) case where topic isn't in state — empty fallback prevents a `KeyError`.
- The Approve button now passes `draft=edited_bodies` AND `paper_title=...` into `graph.update_state`. The state merge is shallow per key, so it overwrites the entire `draft` dict (which is what we want — the user's edited bodies replace the drafter's output completely).
- `.strip('"').strip("'")` on each suggested title handles the LLM occasionally wrapping titles in quotes despite the prompt.
- Per-section `f"draft_{section.title}"` keys give Streamlit stable identity for each text_area.
- Ephemeral key cleanup on Approve covers `title_input`, `title_suggestions`, and the per-section `draft_*` keys.

- [ ] **Step 2: Clean ephemeral UI keys on "➕ New chat"**

Find the "➕ New chat" button handler (around lines 57–69). Currently it's:

```python
    if st.button("➕ New chat", use_container_width=True, type="primary"):
        current_mode = st.session_state.mode
        new_id = str(uuid.uuid4())
        try:
            db.create_paper(new_id, topic="(untitled)", mode=current_mode)
        except Exception as e:
            st.error(f"Could not reach Supabase: {e}")
            st.stop()
        for k, v in defaults.items():
            st.session_state[k] = v if not callable(v) else v
        st.session_state.mode = current_mode
        st.session_state.thread_id = new_id
        st.session_state.checkpointer = get_checkpointer()
        st.session_state.pop("_persisted_complete", None)
        st.rerun()
```

Find the line `st.session_state.pop("_persisted_complete", None)` and immediately after it, add three more pop calls:

```python
        st.session_state.pop("_persisted_complete", None)
        st.session_state.pop("title_input", None)
        st.session_state.pop("title_suggestions", None)
        st.session_state.pop("pending_title", None)
        st.rerun()
```

(`draft_*` keys cycle off naturally because their section titles change between papers, but `title_input` / `title_suggestions` / `pending_title` are fixed-name and would persist.)

- [ ] **Step 3: Clean ephemeral UI keys in the resume block**

Find the resume block (currently around line 273):

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
```

Find the line `st.session_state._persisted_complete = (paper["status"] == "complete")` and immediately after it, add three pop calls:

```python
    st.session_state._persisted_complete = (paper["status"] == "complete")
    st.session_state.pop("title_input", None)
    st.session_state.pop("title_suggestions", None)
    st.session_state.pop("pending_title", None)
```

- [ ] **Step 4: Run the unit suite to confirm no regression**

Run: `.venv/Scripts/python -m pytest --ignore=tests/integration -q`

Expected: 54 passed, 1 skipped. The page isn't exercised by unit tests — this just confirms nothing imports broke.

- [ ] **Step 5: Quick syntax sanity check**

Run: `.venv/Scripts/python -m py_compile pages/1_New_Paper.py`

Expected: no output, exit 0. (Catches indentation / missing-colon errors before Streamlit chokes at runtime.)

- [ ] **Step 6: Commit**

```bash
git add pages/1_New_Paper.py
git commit -m "$(cat <<'EOF'
feat(ui): editable Checkpoint 3 — section bodies, title, suggestions

Replaces the read-only finalize checkpoint with:
- A title text_input pre-filled with state.paper_title (or topic).
- A '✨ Suggest titles' button that calls the LLM page-side at
  temperature 0.7 and renders the results as clickable buttons.
- Per-section editable text_areas. Reviewer issues for each section
  now render inline above the section they concern, not in one
  collapsed expander at the top.
- An Approve handler that pushes both the edited draft dict and the
  chosen paper_title via graph.update_state before resuming.

Ephemeral UI keys (title_input, title_suggestions, pending_title) are
popped on Approve, on '➕ New chat', and in the resume block so they
don't leak between papers.
EOF
)"
```

---

## Phase 3 — Manual smoke

### Task 3: End-to-end browser smoke

**Files:** none — verification only.

Assumes the same `.env` and Supabase project from prior smokes are in place.

- [ ] **Step 1: Start the app**

If Streamlit isn't already running: `streamlit run app.py` in a separate terminal, then open http://localhost:8501.

- [ ] **Step 2: Create a Term Paper through to Checkpoint 3**

Pick **Term Paper** (the fastest mode — single drafter pass, no reviewer loop). Use a short topic like `Photosynthesis basics`. Approve outline → wait for sources → approve sources → wait for drafter. When the page arrives at Checkpoint 3 ("Review draft"), confirm:

- A `📝 Paper title` heading appears at the top.
- A text input is pre-filled with `Photosynthesis basics` (the topic).
- A `✨ Suggest titles` button sits below the input.
- Below the divider, a `📄 Sections` heading is followed by editable text_areas for each section (Introduction, Body, Conclusion), each pre-populated with the drafter's text.
- The bottom button is `✅ Approve → finalize`.

- [ ] **Step 3: Verify title suggestions**

Click `✨ Suggest titles`. After ~3–5 seconds:

- A `Suggestions (click to use):` caption appears.
- 3 (sometimes up to 5) titles render as full-width buttons.

Click one of the suggestions. Confirm:

- The text input value at the top changes to the clicked suggestion.
- The suggestion buttons remain visible (so the user can pick a different one).

- [ ] **Step 4: Verify draft editing**

Edit the first section's text_area — append the sentence `**Edit smoke test marker.**` to its body. Don't approve yet.

- [ ] **Step 5: Verify reviewer issues display (Literature Review path)**

This step is only meaningful in survey or empirical mode (term mode skips the reviewer). Open a new tab on the dashboard, pick **Literature Review**, give a small topic like `BERT pretraining`, and approve outline → sources → wait for drafter + reviewer to run. When Checkpoint 3 appears, IF the reviewer flagged any issues, confirm:

- Each issue is rendered above the section it concerns, NOT in a single collapsed expander at the top.
- The format is `⚠️ Reviewer issues for {section}:` followed by `- [kind] suggestion` bullets.

If the reviewer found no issues (`review.verdict == "pass"`), the inline blocks won't render — that's correct. Move on.

- [ ] **Step 6: Approve and verify the final paper**

Back on the Term Paper. Click `✅ Approve → finalize`. After ~10–30 seconds, the main panel should switch to the completed view with `📑 Paper complete` and the Markdown / PDF download buttons. Click `⬇️ Download Markdown` and open the file. Confirm:

- The H1 line is the title the user chose (the suggestion clicked in Step 3), NOT the original topic.
- The first section's body contains `**Edit smoke test marker.**` from Step 4.

- [ ] **Step 7: Verify cross-paper cleanup**

Click `← Back to dashboard`. In the landing page, click any other paper in "My papers" to resume it. After resume, click into its Checkpoint 3 (if it's at that step) or start a new chat with `➕ New chat`. Confirm:

- The title input does NOT show the previous paper's suggested title — it shows either the new paper's `paper_title` (if persisted) or its topic.
- The "Suggestions" block does NOT show stale suggestions from the previous paper.

- [ ] **Step 8: Stop Streamlit**

Ctrl+C in the terminal running it.

---

## Self-Review (already applied)

**Spec coverage:**
- Goal #1 (editable section bodies) → Task 2 Step 1 (text_area per section).
- Goal #2 (title input with LLM suggestions) → Task 2 Step 1 (title input + Suggest button + pending_title sentinel pattern).
- Architecture (additive PaperState field + finalize change + page rewrite) → Task 1 + Task 2.
- UI layout (per-section issues inline; title row at top; sections inline; Approve at bottom) → Task 2 Step 1.
- State change (`paper_title: str` in PaperState) → Task 1 Step 3.
- Finalize node change (use paper_title with fallback) → Task 1 Step 4.
- Title-suggestion LLM call (page-side, temperature 0.7, 3-5 split lines, sentinel pattern) → Task 2 Step 1.
- Approve flow (push draft + paper_title, then stream until interrupt) → Task 2 Step 1.
- Error handling (LLM fail → st.error; empty title → topic fallback) → Task 1 implementation handles fallback; Task 2 wraps the LLM call in try/except.
- Test changes (new finalize tests covering set + empty) → Task 1 Step 1.
- File touch list (4 files) → Tasks 1 + 2 hit exactly those four files.

**Placeholder scan:** No TBD/TODO/"similar to". Every step has concrete code or commands.

**Type/signature consistency:**
- `PaperState.paper_title` is a `str` field — same in `state.py` definition, in `finalize_node` (`state.get("paper_title")` returns `str | None`), and in `graph.update_state` payload (`st.session_state.title_input` is a `str`).
- `state.get("paper_title") or state["topic"]` correctly handles both missing-key and empty-string cases (covered by both new tests).
- Streamlit keys: `title_input`, `title_suggestions`, `pending_title`, and `draft_{section.title}` are all `str` and distinct from any keys defined elsewhere in the project (grepped: no collisions with `start_`, `resume_`, `del_`, `sb_resume_`, `src{src.id}`, `t{i}`, `b{i}`, `w{i}`).
- `graph.update_state(config(), {"draft": ..., "paper_title": ...})` payload uses the same keys as `PaperState` — LangGraph merges by key, no type mismatch.
- The `outline` iteration in the Approve handler uses `section.title` to look up `edited_bodies[section.title]`, matching the existing drafter pattern of keying `draft` by section title.
