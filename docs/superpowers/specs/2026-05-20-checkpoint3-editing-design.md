# Editable Checkpoint 3 — Design

**Status**: approved
**Date**: 2026-05-20

## Goal

Make Checkpoint 3 ("Review draft", just before finalize) interactive instead of read-only:

1. The user can **edit each section's body** in place, with reviewer issues for that section shown inline as context.
2. The user can **set the paper title** — pre-filled with the original topic, with an on-demand `✨ Suggest titles` button that asks the LLM for 3 academic title options.

Today this checkpoint just lists reviewer issues in a collapsed expander and renders each section read-only with a single "Approve → finalize" button. The user has no way to act on reviewer feedback or override the title.

## Non-goals

- Editing section titles, bullet points, or word targets at this checkpoint (that's Checkpoint 1's responsibility — surfacing it here would create two sources of truth).
- Re-running the reviewer after edits.
- Marking individual reviewer issues as "dismissed" / "resolved" with explicit state (the user's edits are implicit resolution; explicit dismissal adds state for no real payoff).
- Section reordering or adding new sections.
- Persisting the LLM-suggested titles to Supabase (regenerated on demand; they're ephemeral UI state).

## Architecture

A page-only change plus one tiny additive change to `PaperState` and `finalize_node`. No new files, no new tables, no new env vars.

```
Checkpoint 3 (chat-page render branch)
   ├── Title section          ── new ──► (page-side LLM call for suggestions)
   ├── Section editors        ── new
   └── Approve button         ── existing, now passes edited state
                                       │
                                       ▼
                          graph.update_state({"draft": edited_draft,
                                              "paper_title": edited_title})
                                       │
                                       ▼
                          stream_until_interrupt()
                                       │
                                       ▼
                          finalize_node reads state["paper_title"]
                          (falls back to state["topic"] when empty)
```

The title-suggestions LLM call lives **inside the Streamlit page**, not as a graph node. It's an on-demand UI affordance, not a step in the pipeline, and routing it through LangGraph would add a state transition for no benefit.

## UI layout

Replacing the current `cp == "finalize"` branch of `render_checkpoint_card` in `pages/1_New_Paper.py`. The new layout is approximately:

```
Checkpoint 3: Review draft

📝 Paper title
  [ text_input prefilled with state["paper_title"] or topic ]
  [✨ Suggest titles]

  (after click, when st.session_state.title_suggestions is set:)
  Suggestions (click to use):
   [Attention Mechanisms in Transformer Architectures: A Survey]
   [A Comprehensive Review of Self-Attention in Modern NLP]
   [Transformer Attention: From Origins to State-of-the-Art]

📄 Sections

  ── Introduction ──
  ⚠️ Reviewer issues:
    - [missing_citation] mention Vaswani et al. 2017
  [ text_area, prefilled with state["draft"]["Introduction"] ]

  ── Background ──
  [ text_area, prefilled with state["draft"]["Background"] ]

  ...

[ ✅ Approve → finalize ]   (full width, primary)
```

Per-section reviewer issues replace today's single collapsed expander listing all issues — each issue renders directly above the section it concerns. Sections with no issues render without the warning block.

Sections are presented as plain `st.text_area` widgets. The current layout (read-only `st.markdown` inside an `st.expander` with `expanded=False`) is fine for review but poor for editing — every rerun re-collapses the expanders and the user has to re-open each one to see their own edits. The implementer may use `st.expander(..., expanded=True)` instead of inline text_areas if visual grouping is preferred; either works.

## State changes

`agent/state.py`: add one field to `PaperState`:

```python
paper_title: str  # populated at Checkpoint 3; finalize falls back to topic when missing
```

`PaperState` already uses `total=False`, so this is non-breaking.

## Finalize node change

`agent/nodes/finalize.py:39`:

```python
# was
paper = (
    f"# {state['topic']}\n\n"
    ...
)

# becomes
title = state.get("paper_title") or state["topic"]
paper = (
    f"# {title}\n\n"
    ...
)
```

Empty string falls through to `topic` via the `or` — covers the case where the user clears the title input.

## Title-suggestion LLM call

When `✨ Suggest titles` is clicked, the page constructs a short prompt and calls the LLM directly (not via the graph). Pseudocode:

```python
from langchain_openai import ChatOpenAI
from agent.graph import DEFAULT_MODEL

section_titles = [s.title for s in snapshot.values.get("outline", [])]
prompt = (
    f"Suggest 3 concise academic titles for a paper on the topic: {topic}\n"
    f"The paper covers these sections: {', '.join(section_titles)}.\n"
    f"Return one title per line. No numbering, no quotes, no commentary."
)
suggestion_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.7)
response = suggestion_llm.invoke(prompt)
suggestions = [
    line.strip() for line in response.content.split("\n") if line.strip()
][:5]
st.session_state.title_suggestions = suggestions
st.rerun()
```

Stored in `st.session_state.title_suggestions` so they persist across reruns until the user navigates away or clicks Suggest again.

When a suggestion button is clicked, the page must transfer that suggestion into the title input. Streamlit forbids writing to a widget's bound session-state key after the widget has rendered on that script run, so use a deferred pattern:

1. The text input is bound to a stable key, e.g. `key="title_input"`.
2. The suggestion button does NOT write to `title_input` directly. Instead it sets a sentinel: `st.session_state.pending_title = suggestion` and calls `st.rerun()`.
3. At the top of the Checkpoint 3 render branch — BEFORE the text_input is instantiated — drain the sentinel: `if "pending_title" in st.session_state: st.session_state.title_input = st.session_state.pop("pending_title")`.
4. The text input then renders with the suggestion as its current value.

This is a well-known Streamlit pattern; the spec calls it out explicitly because the obvious-looking direct write fails at runtime.

Temperature 0.7 — higher than the rest of the pipeline (0.0 default) — to produce diverse-but-coherent suggestions.

## Approve flow

When the user clicks `✅ Approve → finalize`:

1. Collect text_area values: `new_draft = {section.title: text_area_value, ...}` for each section in the outline (order preserved by iterating `snapshot.values["outline"]`).
2. Read the title input. If empty, fall through (finalize_node handles fallback).
3. Push both into graph state in one update:
   ```python
   graph.update_state(config(), {"draft": new_draft, "paper_title": title_input})
   ```
4. Clear `pending_checkpoint`, run `stream_until_interrupt(None)`. The graph advances from the interrupt to `finalize_node`, which produces `final_output`, which the main panel then renders with the Download buttons.

## Error handling

- **LLM call for title suggestions fails**: catch, show `st.error(f"Couldn't generate suggestions: {e}")`, leave text input untouched. User can still type their own.
- **User clears the title input**: empty string flows into state; `finalize_node` falls back to `state["topic"]` via the `or` clause. No UI guard needed.
- **User makes no edits**: text_area values equal the current draft body, `paper_title` equals the topic. The `graph.update_state` call is a no-op in effect (writes the same values); finalize runs identically to today. Backward compatible.
- **Reviewer issues block**: renders only when `review.issues` for that section is non-empty. Sections with no issues render cleanly.

## Test changes

- `tests/test_finalize.py`: add one new test — `test_finalize_uses_paper_title_when_set`. Build a state with `paper_title="Custom Title"` and verify the rendered Markdown's H1 is `# Custom Title` and not the topic. Keep the existing tests that rely on topic-as-title (they cover the fallback branch).
- No tests for the page-side title-suggestion LLM call. It's a pure UI affordance behind a button — covered by manual smoke if needed.

## File touch list

- `agent/state.py` — add `paper_title` field to `PaperState`.
- `agent/nodes/finalize.py` — use `paper_title` with fallback to topic.
- `pages/1_New_Paper.py` — replace the `cp == "finalize"` branch with the new editable layout, add the suggestion-LLM helper.
- `tests/test_finalize.py` — add the `paper_title` happy-path test.

Four files. No new files. No new dependencies (ChatOpenAI is already imported elsewhere). No schema changes.
