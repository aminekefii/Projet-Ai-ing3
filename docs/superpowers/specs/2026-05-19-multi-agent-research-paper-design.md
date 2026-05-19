# Multi-Agent Research-Paper System — Design Spec

**Date:** 2026-05-19
**Status:** Approved for implementation planning
**Scope:** Evolves the University Writing Assistant from a single ReAct agent that drafts essays into a three-specialist LangGraph state machine that produces research-grade papers with explicit human checkpoints.

---

## 1. Motivation

The current project (`agent/graph.py`) wraps a single ReAct agent that picks one of five tools per turn and emits a Markdown answer. It works well for one-shot questions and short drafts but is structurally weak for longer-form research output:

- A single loop conflates research, drafting, and self-critique — quality plateaus quickly.
- There is no separation between "gather sources" and "write from sources", so citations and prose are produced in the same step (and citations sometimes drift from what was actually retrieved).
- There is no checkpoint where the user can edit an outline or prune sources before drafting starts, so the only feedback loop is "discard the answer and try again".
- The model name `gpt-5.4-mini` in `agent/graph.py:8` is not a real OpenAI model and will 404 at runtime. This needs fixing as a prerequisite.

The redesign keeps everything that works (the 5 tools, the FAISS+FastEmbed RAG pipeline, the Streamlit UI patterns) and replaces only the orchestration layer.

---

## 2. Modes

The system supports three paper modes, selected per-paper at intake:

| Mode | Use case | Differences from default flow |
|---|---|---|
| **survey** (default) | Literature review / synthesis paper | Full graph as described |
| **empirical** | User uploads data (CSV / notes / lab results) | Adds a `data_analyzer` node before `drafter`; `drafter` gets `python_repl` |
| **term** | Standard university term paper / essay | Skips the reviewer revision loop by default (single drafter pass) |

Modes are not separate graphs. They are a small `modes.py` config object swapping prompts, outline templates, and a few conditional edges within the same graph.

---

## 3. Architecture

A LangGraph state graph with three specialist agents and three checkpoint interrupts (topic, sources, draft) plus a terminal download screen. The orchestrator is the graph itself — no LLM supervisor — so routing is deterministic and cheap to debug.

```
user request: topic + mode
            │
            ▼
       ┌─────────┐
       │ intake  │  parse topic, generate outline from mode template
       └────┬────┘
            ▼
  ◇ CHECKPOINT 1: confirm topic + outline
            ▼
       ┌────────────┐
       │ researcher │  ReAct agent over web/arxiv/wiki/docs
       │            │  → sources (8–15, deduped)
       └─────┬──────┘
            ▼
  ◇ CHECKPOINT 2: approve / prune sources
            ▼
    [empirical mode only: data_analyzer]
            ▼
       ┌─────────┐
       │ drafter │  per-section, cites only from source pack
       └────┬────┘
            ▼
       ┌──────────┐
       │ reviewer │  LLM-as-judge → ReviewReport (issues + verdict)
       └────┬─────┘
            ▼
  ◇ revision_needed? ──yes──► drafter (revision pass, max 1)
            │ no
            ▼
  ◇ CHECKPOINT 3: review final draft
            ▼
       ┌──────────┐
       │ finalize │  format export (Markdown / LaTeX)
       └────┬─────┘
            ▼
  ▣ TERMINAL SCREEN: download / copy final output  (not a graph interrupt — graph has ended)
```

### Key architectural decisions

- **Shared state object** (`PaperState`) flows through every node. Each agent reads what it needs and writes its slice. No agent-to-agent message passing other than this shared state.
- **No LLM supervisor.** Routing is a `langgraph.StateGraph` with conditional edges based on state values (mode, revision_count, review.verdict). Deterministic, cheap, easy to test.
- **`langgraph.interrupt()`** at each checkpoint pauses the graph; the Streamlit UI resumes with the user's input. `MemorySaver` (in-process) persists state across interrupts so the user can close the browser tab and return — *as long as the Streamlit server is still running*. State does not survive a server restart (see §10 — cross-session persistence is explicitly out of scope to preserve the in-memory privacy guarantee in §7).
- **One revision loop max** between drafter ↔ reviewer to prevent infinite churn; if the reviewer still flags issues, they surface to the human at checkpoint 3 instead of triggering another revision.
- **Mode is a config object**, not a graph variant. Same wiring, swapped prompts and templates.

---

## 4. Components

### 4.1 `PaperState` — shared graph state

```python
class PaperState(TypedDict):
    topic: str                    # user's original request
    mode: Literal["survey", "empirical", "term"]
    outline: list[Section]        # [{title, bullets, target_words}]
    user_data: list[Document]     # uploaded PDFs/CSVs (empirical mode)
    sources: list[Source]         # [{id, title, authors, year, url, snippet, origin_tool, covers_sections}]
    draft: dict[str, str]         # {section_title: markdown_body}
    review: ReviewReport          # {issues: [...], verdict: "pass" | "revise"}
    revision_count: int           # 0 or 1
    token_usage: dict             # {input, output, total, budget, warning, halt}
    messages: list[BaseMessage]   # full trace for the UI
```

`Source`, `Section`, `ReviewReport` are Pydantic models for validation at every node boundary.

### 4.2 Agent 1 — `researcher` (ReAct sub-agent)

- **Job:** given `topic` + `outline`, gather a balanced source pack covering every outline section.
- **Reads:** `topic`, `outline`, `mode`, `user_data`
- **Writes:** `sources` (deduped by URL/DOI, target 8–15 entries)
- **Tools:** `web_search`, `wikipedia`, `arxiv`, `document_search` (when files uploaded). Reuses today's `agent/tools.py` verbatim.
- **Cap:** 12 tool calls per run.
- **Prompt:** "For each outline section, find 2–3 reputable sources. Prefer peer-reviewed (arXiv) over Wikipedia. Return a deduped JSON list with `{id, title, authors, year, url, snippet, covers_sections}`."

### 4.3 Agent 2 — `drafter` (per-section drafter, called in a loop over outline)

- **Job:** draft one section at a time using only the `sources` already gathered. Inline-cites with `[source_id]`.
- **Reads:** `outline[i]`, `sources`, `mode`, `draft` so far (for context continuity)
- **Writes:** `draft[section.title]`
- **Tools:** none, except `python_repl` in empirical mode for stats on `user_data`. Cap: 5 tool calls in empirical mode, 0 otherwise.
- **Prompt:** mode-specific. Hard rule: every factual claim cites a source from the pack; no invented citations.

### 4.4 Agent 3 — `reviewer` (LLM-as-judge, no tools)

- **Job:** read the full draft against the outline and source pack, produce a structured `ReviewReport`.
- **Reads:** `outline`, `draft`, `sources`
- **Writes:** `review` = `{issues: [{section, kind: missing_citation|weak_argument|off_topic|repetition, suggestion}], verdict: pass | revise}`
- **Routing:** if `verdict == "revise"` AND `revision_count == 0`, increment and loop back to drafter with the issues injected into the drafter's prompt. Otherwise advance to checkpoint 3.

### 4.5 Mode profiles (`agent/modes.py`)

Each mode is a dataclass with `outline_template`, `researcher_prompt_addendum`, `drafter_prompt_addendum`, `default_sections`, `skip_reviewer_revision` (bool). Nodes read the profile from `state["mode"]`.

### 4.6 File layout (delta from today)

```
agent/
├── graph.py          # rewritten: state graph build, not single ReAct agent
├── state.py          # NEW: PaperState, Source, Section, ReviewReport pydantic models
├── modes.py          # NEW: survey/empirical/term profiles
├── nodes/            # NEW: one file per node
│   ├── __init__.py
│   ├── intake.py
│   ├── researcher.py    # wraps a ReAct sub-agent
│   ├── drafter.py
│   ├── data_analyzer.py # empirical mode only
│   ├── reviewer.py
│   └── finalize.py
├── validators.py     # NEW: citation validator, budget tracker, schema validation helpers
├── tools.py          # unchanged
├── prompts.py        # expanded with per-agent + per-mode prompts
└── rag.py            # unchanged
```

`app.py` rewires to call `graph.invoke(...)` / `graph.stream(...)` and renders the four checkpoint interrupts as approval cards.

---

## 5. Data flow & checkpoint UX

### 5.1 End-to-end trace (survey mode)

| Step | Node | Reads | Writes | UI shows |
|---|---|---|---|---|
| 1 | `intake` | `topic`, `mode` | `outline` | "Proposed topic and outline" card |
| 2 | **interrupt #1** | — | `outline` (possibly edited) | Editable outline → Approve / Edit / Regenerate |
| 3 | `researcher` | `topic`, `outline` | `sources` | Live tool-call stream (reuses today's `st.status` boxes) |
| 4 | **interrupt #2** | — | `sources` (possibly pruned) | Source-pack table → Approve / Drop selected / Find more |
| 5 | `drafter` (loop) | `outline[i]`, `sources`, `draft` | `draft[section]` | Sections stream in as written; `[src-3]` refs are clickable |
| 6 | `reviewer` | `outline`, `draft`, `sources` | `review` | Collapsed ReviewReport with issue count + verdict |
| 7 | conditional edge | `review.verdict`, `revision_count` | — | If revising: "Reviewer flagged N issues, drafter is revising…" |
| 8 | `drafter` (revision) | `review.issues`, prior `draft` | `draft` (updated) | Diff view of changed sections |
| 9 | **interrupt #3** | — | `draft` (possibly edited) | Full draft preview → Approve & finalize / Request changes |
| 10 | `finalize` | `draft`, `sources`, `mode` | `final_output` | Download buttons (Markdown / LaTeX), copy-to-clipboard |

### 5.2 LangGraph ↔ Streamlit interrupt wiring

```python
# graph.py
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["researcher", "drafter", "finalize"],
)

# app.py
config = {"configurable": {"thread_id": st.session_state.thread_id}}

if st.session_state.pending_checkpoint is None:
    for event in graph.stream(input_or_None, config=config, stream_mode="updates"):
        render_event(event)
    snapshot = graph.get_state(config)
    if snapshot.next:                       # graph paused at an interrupt
        st.session_state.pending_checkpoint = snapshot.next[0]
        st.rerun()
else:
    render_checkpoint_card(st.session_state.pending_checkpoint, graph.get_state(config))
    # On approval:
    graph.update_state(config, edited_values)   # if user edited anything
    st.session_state.pending_checkpoint = None
    st.rerun()
```

The user can close the browser tab between any two checkpoints — `MemorySaver` keyed by `thread_id` keeps the paper in-flight for the lifetime of the Streamlit process. Reopening the tab hydrates state and shows the next pending checkpoint. A Streamlit server restart loses in-flight papers (see §10).

### 5.3 Checkpoint card pattern (consistent across the three interrupt cards)

The terminal download screen uses a simpler download-only variant (no approve/edit/regenerate row). Each interrupt card has:
1. **Summary** at top (one sentence: "I drafted a 5-section outline based on your topic")
2. **The artifact**, editable in place (outline → text areas per section; sources → table with checkboxes; draft → expandable per-section markdown)
3. **Action row** at bottom (Approve → / Edit & approve / Regenerate this step / Cancel paper)
4. **Cost meter** (running token + estimated USD so the user knows what each step cost)

---

## 6. Error handling

Tool-level resilience already exists in `agent/tools.py` (`_safe()` returns error strings to the agent). Keep it. Add the following agent-level handling:

| Failure mode | Detection | Recovery |
|---|---|---|
| Researcher returns < 3 sources after 6 tool calls | Count sources + tool-call budget after node | Surface at checkpoint #2: "Only found N sources — proceed, broaden topic, or upload more readings?" |
| Drafter hallucinates a citation (`[src-99]` not in pack) | Post-draft regex scan validates all `[src-N]` refs | Strip invalid refs, append to `review.issues` as `missing_citation`, force revision pass even if reviewer didn't flag it |
| Drafter ignores outline | Reviewer catches as `off_topic` | Normal revision loop |
| Reviewer loops forever | Hard cap: `revision_count == 1` advances regardless of verdict | Built into the conditional edge |
| Malformed JSON from LLM (sources, review) | Pydantic validation on every structured output; retry once with error in prompt | After 2 failures, downgrade to text-mode output and surface partial result |
| OpenAI rate limit / 5xx | `tenacity` retry: 3 attempts, exponential backoff (1s, 4s, 16s) | If still failing, halt at the current node and show "OpenAI is unavailable — your paper is paused. Reload the tab to retry (state held in-process until server restart)." |
| Invalid model name | Validation at `build_graph()` against an allowlist of known-good models | Fail fast with clear error instead of mid-run 404 |

### Failure UX

Every failure surfaces through one of three patterns:
1. **Inline toast** — transient (rate-limit retried successfully)
2. **Checkpoint warning banner** — non-fatal but worth flagging at next human checkpoint
3. **Halt + resume card** — fatal mid-run (budget hit, repeated 5xx, user cancel): paper paused at the current node, `thread_id` shown, "Resume" button reloads from `MemorySaver`. Recovery works for the lifetime of the Streamlit process; a server restart loses in-flight papers (intentional — see §7 privacy guarantee and §10 out-of-scope).

---

## 7. Guardrails (cost & safety)

A multi-agent paper run can burn $1–$5 in tokens if unchecked. Hard caps:

- **Per-paper token budget** — default 200k tokens. Tracked in `PaperState.token_usage`. 80% triggers a warning at the next checkpoint; 100% halts at the next node and requires explicit user override.
- **Per-node max tool calls** — researcher: 12, drafter: 0 (5 in empirical mode), reviewer: 0.
- **Source-count caps** — researcher returns at most 15 sources; over-cap entries are truncated with a note.
- **Section length caps** — drafter respects `outline[i].target_words ± 20%`; over-cap drafts truncate and re-prompt once.
- **Document-search privacy** — uploaded readings stay in-memory (current FAISS in `st.session_state`); never persisted, never sent to logging. Keep current behavior, document it explicitly.
- **No external writes** — agents have no shell, no filesystem write, no API calls beyond the 5 read-only tools. The only side effect is the final download the user clicks to save.

---

## 8. Testing strategy

### 8.1 Layer 1 — Unit tests (pytest, no API calls, fast)

Pure-function tests that run without an OpenAI key:

- State transitions — feed synthetic `PaperState` to each node's pure helpers (outline parser, source deduper, citation extractor, budget tracker). Assert state-out shape.
- Mode profiles — each profile (survey/empirical/term) loads, has the required keys, produces a valid outline template.
- Citation validator — `extract_citations("text with [src-1] and [src-99]")` returns `{"src-1", "src-99"}`. Given source pack `["src-1"]`, validator flags `src-99` as missing.
- Pydantic schemas — `Source`, `Section`, `ReviewReport`, `PaperState` reject malformed inputs.
- Budget tracker — adding tokens crosses 80% sets `warning=True`, crosses 100% sets `halt=True`.

Goal: ~30 tests, run in <2 seconds, no network.

### 8.2 Layer 2 — Integration tests (real API, slow, gated by `OPENAI_API_KEY`)

Evolve today's `verify.py` into `verify_pipeline.py`. Same harness style (no pytest dependency, prints PASS/FAIL, exits non-zero on failure).

- **Full survey run** — topic "transformer attention mechanisms", checkpoints auto-approved. Assert ≥6 sources gathered, all draft citations resolve to a source ID, reviewer verdict is `pass` or one revision pass occurred, final draft has all outline sections.
- **Empirical run** — upload fixture CSV (`tests/fixtures/sales_data.csv`), topic "trends in Q3 sales", assert `data_analyzer` ran `python_repl` and the draft references at least one computed statistic.
- **Term-paper run** — confirms reviewer revision loop is skipped by default.
- **Resume across interrupt** — start a run, drop the graph object, reload from `MemorySaver` with same thread_id, confirm resume at same node with state intact.
- **Citation-validator integration** — inject a draft containing fake `[src-99]`, confirm post-draft scan catches it and forces a revision.
- **Budget halt** — set budget to 5k tokens, start a run, confirm graph halts at the next checkpoint with `halt=True` and state preserved.

README documents: "Run `python verify_pipeline.py` before any PR that touches the graph."

### 8.3 Layer 3 — Golden-output snapshot (one test)

`tests/golden/` contains a fixed-topic survey run with `temperature=0` and a pinned model. Asserts the final outline structure (section titles, count) against a committed snapshot. Detects unintentional prompt regressions. Snapshot is *outline shape only*, not prose — prose varies even at temp 0 across model versions, and asserting on prose creates maintenance tax with no signal.

### 8.4 What we do not test

- The exact prose of generated sections (too brittle).
- The web/wiki/arxiv tools themselves (upstream libraries, already covered by today's `verify.py`).
- Cross-model behavior (pin one model in CI; budget guardrail catches cost surprise of swapping).

### 8.5 Manual UI smoke checklist

Per project instructions to test UI changes in a browser: `streamlit run app.py`, then for each mode walk one paper end-to-end. Confirm each checkpoint card renders, editing the artifact persists, "Cancel paper" cleans state, and browser-close-and-reopen lands on the same checkpoint.

---

## 9. Prerequisites (must land before main work)

1. **Fix the model name.** `agent/graph.py:8` and the README both reference `gpt-5.4-mini`, which is not a real OpenAI model and will 404. Replace with a real model (`gpt-4o-mini` or `gpt-5-mini`, whichever the user prefers) and add the model-name allowlist validator from §6.
2. **Delete `txt.txt`** — scratch file with no purpose.
3. **De-hard-code the verify path.** `verify.py:156` points to `C:/Users/amine/Downloads/CAHIER_DE_CHARGE_D_TAILL_.pdf`. Either skip the RAG check cleanly when the file is missing or read the path from an env var. (Will be superseded by `verify_pipeline.py` anyway, but should not block landing before then.)

---

## 10. Out of scope (explicitly not in this spec)

- A web-hosted version (stays local Streamlit).
- Multi-user accounts / authentication.
- Persisting papers to disk between Streamlit server sessions (in-memory `MemorySaver` only, per the §7 privacy guardrail — swapping in `SqliteSaver` for cross-restart resume is deliberately deferred).
- LaTeX rendering preview (export-only; user pastes into Overleaf).
- A 4th mode (e.g., grant proposal, dissertation chapter) — easy to add later via `modes.py`, not in v1.
- Replacing FastEmbed/FAISS with anything else.
- Swapping LangGraph for another framework.

---

## 11. Open questions for the user

None at design time. The model-name choice (gpt-4o-mini vs gpt-5-mini) will be confirmed during planning.
