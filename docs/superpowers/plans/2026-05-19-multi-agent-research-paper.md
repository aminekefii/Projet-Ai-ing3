# Multi-Agent Research-Paper System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single ReAct agent in `agent/graph.py` with a 3-specialist LangGraph state machine (researcher → drafter → reviewer) that produces research papers in three modes (survey / empirical / term), with three human checkpoint interrupts and a terminal download screen.

**Architecture:** A LangGraph `StateGraph` with a shared `PaperState`. Nodes communicate only through state. `interrupt_before` pauses at three points (`researcher`, `drafter`, `finalize`) for human approval; Streamlit resumes via `graph.update_state()`. Modes are a single config object that swaps prompts, not three separate graphs.

**Tech Stack:** Python 3.11+, LangGraph, langchain-openai, pydantic, FAISS, FastEmbed, pypdf, Streamlit, tenacity, pytest.

**Spec:** `docs/superpowers/specs/2026-05-19-multi-agent-research-paper-design.md`

---

## File Structure

**Created:**
- `agent/state.py` — Pydantic models (`Section`, `Source`, `ReviewIssue`, `ReviewReport`, `TokenUsage`) + `PaperState` TypedDict
- `agent/modes.py` — `ModeProfile` dataclass + three profiles (survey/empirical/term)
- `agent/validators.py` — pure functions: citation extractor, budget tracker, model-name allowlist
- `agent/nodes/__init__.py`
- `agent/nodes/intake.py` — produces initial outline from topic + mode
- `agent/nodes/researcher.py` — wraps a ReAct sub-agent over the 4 tools, returns `sources`
- `agent/nodes/drafter.py` — per-section drafter with citation enforcement
- `agent/nodes/reviewer.py` — LLM-as-judge producing `ReviewReport`
- `agent/nodes/data_analyzer.py` — empirical-mode-only stats on user data
- `agent/nodes/finalize.py` — formats final Markdown/LaTeX output
- `tests/__init__.py`
- `tests/conftest.py` — pytest fixtures (synthetic state, source pack, etc.)
- `tests/test_state.py`
- `tests/test_validators.py`
- `tests/test_modes.py`
- `tests/test_intake.py`
- `tests/test_drafter.py`
- `tests/test_reviewer.py`
- `tests/test_finalize.py`
- `tests/golden/test_outline_snapshot.py`
- `tests/golden/survey_attention_outline.json`
- `tests/fixtures/sales_data.csv`
- `verify_pipeline.py` — end-to-end integration harness (replaces today's `verify.py`)
- `pytest.ini`

**Modified:**
- `agent/graph.py` — rewritten: builds and compiles the StateGraph instead of a single ReAct agent
- `agent/prompts.py` — adds per-agent and per-mode prompt templates; keeps `get_prompt()` for back-compat during transition
- `app.py` — replaces single-turn streaming with checkpoint-card UI
- `requirements.txt` — adds `pydantic`, `tenacity`, `pytest`
- `README.md` — updates run instructions, adds mode descriptions

**Deleted:**
- `txt.txt` (scratch file, no purpose)
- `verify.py` (replaced by `verify_pipeline.py`)

---

## Task 1: Prerequisites — fix model name, delete scratch files, add deps

**Files:**
- Modify: `agent/graph.py:8`
- Modify: `README.md` (model references)
- Modify: `requirements.txt`
- Delete: `txt.txt`

- [ ] **Step 1: Pick a real model name**

Open `agent/graph.py`, replace `DEFAULT_MODEL = "gpt-5.4-mini"` with a real OpenAI model. Default to `gpt-4o-mini` (cheap, fast, available). If the user explicitly prefers `gpt-5-mini` during planning, use that instead.

```python
# agent/graph.py:8
DEFAULT_MODEL = "gpt-4o-mini"
```

- [ ] **Step 2: Update README model reference**

In `README.md`, find the line `**LLM**: [OpenAI](https://openai.com) — \`gpt-5.4-mini\`` and replace with `**LLM**: [OpenAI](https://openai.com) — \`gpt-4o-mini\` (configurable)`.

- [ ] **Step 3: Add new dependencies**

Append to `requirements.txt`:

```
pydantic>=2.9.0
tenacity>=9.0.0
pytest>=8.3.0
```

- [ ] **Step 4: Delete scratch file**

```bash
rm txt.txt
```

- [ ] **Step 5: Install new deps**

```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

Expected: clean install, no errors.

- [ ] **Step 6: Commit**

```bash
git add agent/graph.py README.md requirements.txt
git rm txt.txt
git commit -m "chore: fix invalid model name, add core deps, drop scratch file"
```

---

## Task 2: Set up tests/ directory and pytest config

**Files:**
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 2: Create `tests/__init__.py`**

Empty file.

- [ ] **Step 3: Create `tests/conftest.py` with shared fixtures**

```python
"""Shared pytest fixtures — no API keys required."""
import pytest


@pytest.fixture
def sample_source_pack():
    """Three sources covering Introduction and Background."""
    from agent.state import Source
    return [
        Source(id="src-1", title="Attention Is All You Need", authors=["Vaswani et al."],
               year=2017, url="https://arxiv.org/abs/1706.03762", snippet="Transformer architecture.",
               origin_tool="arxiv", covers_sections=["Introduction", "Background"]),
        Source(id="src-2", title="BERT", authors=["Devlin et al."],
               year=2018, url="https://arxiv.org/abs/1810.04805", snippet="Bidirectional encoders.",
               origin_tool="arxiv", covers_sections=["Background"]),
        Source(id="src-3", title="Transformer (Wikipedia)", authors=[],
               year=None, url="https://en.wikipedia.org/wiki/Transformer",
               snippet="Overview of transformer model.", origin_tool="wikipedia",
               covers_sections=["Introduction"]),
    ]


@pytest.fixture
def sample_outline():
    from agent.state import Section
    return [
        Section(title="Introduction", bullets=["context", "thesis"], target_words=400),
        Section(title="Background", bullets=["history"], target_words=600),
    ]


@pytest.fixture
def sample_state(sample_source_pack, sample_outline):
    from agent.state import TokenUsage
    return {
        "topic": "Transformer attention mechanisms",
        "mode": "survey",
        "outline": sample_outline,
        "user_data": [],
        "sources": sample_source_pack,
        "draft": {},
        "review": None,
        "revision_count": 0,
        "token_usage": TokenUsage(),
        "messages": [],
        "final_output": None,
    }
```

- [ ] **Step 4: Verify pytest discovers nothing yet (clean baseline)**

```bash
.venv/Scripts/python -m pytest
```

Expected: `collected 0 items`, exit 0 (or `no tests ran`).

- [ ] **Step 5: Commit**

```bash
git add pytest.ini tests/__init__.py tests/conftest.py
git commit -m "test: scaffold tests/ with pytest config and shared fixtures"
```

---

## Task 3: Implement `state.py` (Pydantic models + PaperState TypedDict)

**Files:**
- Create: `agent/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_state.py
import pytest
from pydantic import ValidationError


def test_section_defaults():
    from agent.state import Section
    s = Section(title="Intro")
    assert s.bullets == []
    assert s.target_words == 500


def test_source_requires_id_title_origin_tool():
    from agent.state import Source
    s = Source(id="src-1", title="t", origin_tool="arxiv")
    assert s.authors == []
    assert s.year is None


def test_source_origin_tool_must_be_allowed():
    from agent.state import Source
    with pytest.raises(ValidationError):
        Source(id="src-1", title="t", origin_tool="random_tool")


def test_review_report_verdict_must_be_pass_or_revise():
    from agent.state import ReviewReport
    with pytest.raises(ValidationError):
        ReviewReport(verdict="maybe")


def test_review_issue_kind_constraints():
    from agent.state import ReviewIssue
    with pytest.raises(ValidationError):
        ReviewIssue(section="Intro", kind="nonsense", suggestion="x")


def test_token_usage_defaults():
    from agent.state import TokenUsage
    u = TokenUsage()
    assert u.total == 0
    assert u.budget == 200_000
    assert u.warning is False
    assert u.halt is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/python -m pytest tests/test_state.py
```

Expected: `ModuleNotFoundError: No module named 'agent.state'`.

- [ ] **Step 3: Implement `agent/state.py`**

```python
"""Shared graph state and validated models for the multi-agent research-paper system."""
from __future__ import annotations

from typing import Literal, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class Section(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)
    target_words: int = 500


class Source(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    url: Optional[str] = None
    snippet: str = ""
    origin_tool: Literal["web_search", "wikipedia", "arxiv", "document_search"]
    covers_sections: list[str] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    section: str
    kind: Literal["missing_citation", "weak_argument", "off_topic", "repetition"]
    suggestion: str


class ReviewReport(BaseModel):
    issues: list[ReviewIssue] = Field(default_factory=list)
    verdict: Literal["pass", "revise"]


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0
    total: int = 0
    budget: int = 200_000
    warning: bool = False
    halt: bool = False


class PaperState(TypedDict, total=False):
    topic: str
    mode: Literal["survey", "empirical", "term"]
    outline: list[Section]
    user_data: list[Document]
    sources: list[Source]
    draft: dict[str, str]
    review: Optional[ReviewReport]
    revision_count: int
    token_usage: TokenUsage
    messages: list[BaseMessage]
    final_output: Optional[str]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/python -m pytest tests/test_state.py
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/state.py tests/test_state.py
git commit -m "feat(agent): add Pydantic state models and PaperState TypedDict"
```

---

## Task 4: Implement `validators.py` (citation extractor, budget tracker, model allowlist)

**Files:**
- Create: `agent/validators.py`
- Create: `tests/test_validators.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_validators.py
import pytest


def test_extract_citations_finds_all():
    from agent.validators import extract_citations
    text = "Claim one [src-1]. Claim two [src-42]. No cite here."
    assert extract_citations(text) == {"src-1", "src-42"}


def test_extract_citations_handles_empty():
    from agent.validators import extract_citations
    assert extract_citations("") == set()


def test_find_missing_citations_returns_unknown_only():
    from agent.validators import find_missing_citations
    text = "Real [src-1], fake [src-99], real [src-2]."
    assert find_missing_citations(text, {"src-1", "src-2"}) == {"src-99"}


def test_budget_warning_at_80_percent():
    from agent.state import TokenUsage
    from agent.validators import update_budget
    usage = TokenUsage(budget=10_000)
    new = update_budget(usage, input_tokens=8_000, output_tokens=0)
    assert new.warning is True
    assert new.halt is False


def test_budget_halt_at_100_percent():
    from agent.state import TokenUsage
    from agent.validators import update_budget
    usage = TokenUsage(budget=10_000)
    new = update_budget(usage, input_tokens=10_000, output_tokens=0)
    assert new.halt is True


def test_budget_accumulates():
    from agent.state import TokenUsage
    from agent.validators import update_budget
    usage = TokenUsage(budget=10_000)
    after1 = update_budget(usage, 1_000, 500)
    after2 = update_budget(after1, 2_000, 500)
    assert after2.total == 4_000


def test_model_name_allowlist_accepts_known():
    from agent.validators import validate_model_name
    validate_model_name("gpt-4o-mini")  # should not raise


def test_model_name_allowlist_rejects_fake():
    from agent.validators import validate_model_name
    with pytest.raises(ValueError, match="not in allowlist"):
        validate_model_name("gpt-5.4-mini")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_validators.py
```

Expected: `ModuleNotFoundError: No module named 'agent.validators'`.

- [ ] **Step 3: Implement `agent/validators.py`**

```python
"""Pure validation helpers — no LLM calls, no I/O. Safe to call from any node."""
from __future__ import annotations

import re

from .state import TokenUsage

CITATION_PATTERN = re.compile(r"\[(src-\d+)\]")

MODEL_ALLOWLIST = frozenset({
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-5-mini",
    "gpt-5",
})


def extract_citations(text: str) -> set[str]:
    """Return the set of citation IDs (like 'src-3') that appear in the text."""
    return set(CITATION_PATTERN.findall(text))


def find_missing_citations(text: str, known_ids: set[str]) -> set[str]:
    """Return citation IDs in the text that are NOT in the known source pack."""
    return extract_citations(text) - known_ids


def update_budget(usage: TokenUsage, input_tokens: int, output_tokens: int) -> TokenUsage:
    """Return a new TokenUsage with accumulated tokens and updated warning/halt flags."""
    new_input = usage.input + input_tokens
    new_output = usage.output + output_tokens
    new_total = new_input + new_output
    return TokenUsage(
        input=new_input,
        output=new_output,
        total=new_total,
        budget=usage.budget,
        warning=new_total >= int(usage.budget * 0.8),
        halt=new_total >= usage.budget,
    )


def validate_model_name(name: str) -> None:
    """Raise ValueError if the model name is not in the allowlist."""
    if name not in MODEL_ALLOWLIST:
        raise ValueError(
            f"Model {name!r} is not in allowlist. "
            f"Allowed: {sorted(MODEL_ALLOWLIST)}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_validators.py
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/validators.py tests/test_validators.py
git commit -m "feat(agent): add validators (citations, budget tracker, model allowlist)"
```

---

## Task 5: Implement `modes.py` (three profile dataclasses)

**Files:**
- Create: `agent/modes.py`
- Create: `tests/test_modes.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_modes.py
import pytest


def test_all_three_profiles_load():
    from agent.modes import PROFILES
    assert set(PROFILES.keys()) == {"survey", "empirical", "term"}


def test_get_profile_returns_correct_mode():
    from agent.modes import get_profile
    assert get_profile("survey").name == "survey"
    assert get_profile("empirical").name == "empirical"
    assert get_profile("term").name == "term"


def test_get_profile_raises_for_unknown_mode():
    from agent.modes import get_profile
    with pytest.raises(ValueError, match="Unknown mode"):
        get_profile("dissertation")


def test_each_profile_has_non_empty_sections():
    from agent.modes import PROFILES
    for name, profile in PROFILES.items():
        assert len(profile.default_sections) >= 3, f"{name} has fewer than 3 sections"
        for section in profile.default_sections:
            assert section.title
            assert section.target_words > 0


def test_term_mode_skips_reviewer_revision():
    from agent.modes import get_profile
    assert get_profile("term").skip_reviewer_revision is True
    assert get_profile("survey").skip_reviewer_revision is False
    assert get_profile("empirical").skip_reviewer_revision is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_modes.py
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `agent/modes.py`**

```python
"""Mode profiles — same graph, swapped prompts and templates."""
from __future__ import annotations

from dataclasses import dataclass, field

from .state import Section


@dataclass
class ModeProfile:
    name: str
    default_sections: list[Section]
    researcher_addendum: str
    drafter_addendum: str
    skip_reviewer_revision: bool = False


SURVEY = ModeProfile(
    name="survey",
    default_sections=[
        Section(title="Introduction", target_words=400),
        Section(title="Background", target_words=600),
        Section(title="Related Work", target_words=800),
        Section(title="Discussion", target_words=600),
        Section(title="Conclusion", target_words=300),
    ],
    researcher_addendum=(
        "Focus on landmark and recent peer-reviewed work. "
        "Prefer arXiv and journal sources over Wikipedia for substantive claims."
    ),
    drafter_addendum=(
        "Adopt the register of a literature review: synthesize multiple sources per "
        "paragraph, contrast positions, do not introduce claims beyond the source pack."
    ),
)

EMPIRICAL = ModeProfile(
    name="empirical",
    default_sections=[
        Section(title="Introduction", target_words=400),
        Section(title="Methods", target_words=500),
        Section(title="Results", target_words=700),
        Section(title="Discussion", target_words=600),
        Section(title="Conclusion", target_words=300),
    ],
    researcher_addendum=(
        "Find prior work relevant to the user's empirical data. "
        "The user supplies the data itself; the source pack contextualizes it."
    ),
    drafter_addendum=(
        "In Methods and Results, ground every quantitative claim in the analyzer's "
        "computed stats (passed via state). Cite external sources only for prior work."
    ),
)

TERM = ModeProfile(
    name="term",
    default_sections=[
        Section(title="Introduction", target_words=300),
        Section(title="Body", target_words=1200),
        Section(title="Conclusion", target_words=300),
    ],
    researcher_addendum="Find 4-8 sources covering the main argument. Quality over quantity.",
    drafter_addendum="Argumentative essay register. Clear thesis, topic sentences, hedged but assertive.",
    skip_reviewer_revision=True,
)

PROFILES: dict[str, ModeProfile] = {
    "survey": SURVEY,
    "empirical": EMPIRICAL,
    "term": TERM,
}


def get_profile(mode: str) -> ModeProfile:
    if mode not in PROFILES:
        raise ValueError(f"Unknown mode {mode!r}. Allowed: {sorted(PROFILES)}")
    return PROFILES[mode]
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_modes.py
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/modes.py tests/test_modes.py
git commit -m "feat(agent): add mode profiles (survey, empirical, term)"
```

---

## Task 6: Implement `nodes/intake.py` (outline generation)

**Files:**
- Create: `agent/nodes/__init__.py`
- Create: `agent/nodes/intake.py`
- Create: `tests/test_intake.py`

- [ ] **Step 1: Create empty `agent/nodes/__init__.py`**

```python
```

- [ ] **Step 2: Write failing tests using a fake LLM**

```python
# tests/test_intake.py
import json

from langchain_core.messages import AIMessage


class FakeLLM:
    """Returns a canned JSON response. Mimics ChatOpenAI.invoke()."""
    def __init__(self, response: str):
        self._response = response

    def invoke(self, messages):
        return AIMessage(content=self._response)


def test_intake_returns_outline_from_llm():
    from agent.nodes.intake import intake_node
    fake = FakeLLM(json.dumps({
        "sections": [
            {"title": "Introduction", "bullets": ["context"], "target_words": 400},
            {"title": "Background", "bullets": ["history"], "target_words": 600},
        ]
    }))
    state = {"topic": "X", "mode": "survey"}
    result = intake_node(state, fake)
    assert len(result["outline"]) == 2
    assert result["outline"][0].title == "Introduction"
    assert result["revision_count"] == 0


def test_intake_respects_mode_default_sections():
    """Empirical mode should produce Methods/Results sections by default."""
    from agent.nodes.intake import intake_node
    # LLM that echoes back the default template
    fake = FakeLLM(json.dumps({
        "sections": [
            {"title": "Methods", "bullets": [], "target_words": 500},
            {"title": "Results", "bullets": [], "target_words": 700},
        ]
    }))
    state = {"topic": "Q3 sales", "mode": "empirical"}
    result = intake_node(state, fake)
    titles = [s.title for s in result["outline"]]
    assert "Methods" in titles
    assert "Results" in titles


def test_intake_raises_on_unknown_mode():
    import pytest
    from agent.nodes.intake import intake_node
    fake = FakeLLM("{}")
    with pytest.raises(ValueError, match="Unknown mode"):
        intake_node({"topic": "X", "mode": "dissertation"}, fake)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_intake.py
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `agent/nodes/intake.py`**

```python
"""Intake node: turn (topic, mode) into a structured outline."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..modes import get_profile
from ..state import PaperState, Section

INTAKE_SYSTEM = """You are an academic editor. Given a topic and a mode, produce a JSON outline.

Respond with EXACTLY this JSON shape (no markdown fence, no commentary):
{"sections": [{"title": "...", "bullets": ["...", "..."], "target_words": 500}]}

Base the section TITLES on the mode's default template (do not invent new ones). \
Tailor the BULLETS to the specific topic — 2-4 concrete points per section."""


def intake_node(state: PaperState, llm) -> dict:
    profile = get_profile(state["mode"])
    default_dump = [s.model_dump() for s in profile.default_sections]
    user_msg = (
        f"Topic: {state['topic']}\n"
        f"Mode: {state['mode']}\n"
        f"Default sections (use these titles and target_words; customize bullets):\n"
        f"{json.dumps(default_dump, indent=2)}"
    )
    resp = llm.invoke([
        SystemMessage(content=INTAKE_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    data = json.loads(resp.content)
    sections = [Section(**s) for s in data["sections"]]
    return {"outline": sections, "revision_count": 0}
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_intake.py
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/nodes/__init__.py agent/nodes/intake.py tests/test_intake.py
git commit -m "feat(nodes): add intake node for outline generation"
```

---

## Task 7: Implement `nodes/researcher.py` (ReAct sub-agent over tools)

**Files:**
- Create: `agent/nodes/researcher.py`
- Modify: `agent/prompts.py` (add researcher prompt)

The researcher reuses today's `agent/tools.py` (`web_search`, `wikipedia`, `arxiv`, optional `document_search`) via a LangGraph ReAct sub-agent. It's prompted to return structured JSON, which we then parse into `Source` objects.

Note: this node is exercised end-to-end in `verify_pipeline.py` (Task 13), not by a unit test, because mocking 4 tools + a ReAct loop has no signal. Unit-test coverage stays on the JSON parsing.

- [ ] **Step 1: Write failing test for the JSON parser only**

```python
# tests/test_researcher.py (NEW)
import pytest


def test_parse_sources_payload_happy_path():
    from agent.nodes.researcher import parse_sources_payload
    payload = """[
        {"id": "src-1", "title": "Attention", "authors": ["Vaswani"],
         "year": 2017, "url": "https://arxiv.org/...", "snippet": "...",
         "origin_tool": "arxiv", "covers_sections": ["Introduction"]}
    ]"""
    sources = parse_sources_payload(payload)
    assert len(sources) == 1
    assert sources[0].id == "src-1"


def test_parse_sources_payload_dedupes_by_url():
    from agent.nodes.researcher import parse_sources_payload
    payload = """[
        {"id": "src-1", "title": "A", "url": "https://x", "origin_tool": "arxiv"},
        {"id": "src-2", "title": "A duplicate", "url": "https://x", "origin_tool": "arxiv"}
    ]"""
    sources = parse_sources_payload(payload)
    assert len(sources) == 1


def test_parse_sources_payload_caps_at_15():
    from agent.nodes.researcher import parse_sources_payload
    items = [{"id": f"src-{i}", "title": f"t{i}", "url": f"u{i}", "origin_tool": "arxiv"}
             for i in range(20)]
    import json
    sources = parse_sources_payload(json.dumps(items))
    assert len(sources) == 15


def test_parse_sources_payload_strips_markdown_fence():
    """LLMs sometimes wrap JSON in ```json fences. Parser must tolerate that."""
    from agent.nodes.researcher import parse_sources_payload
    payload = '```json\n[{"id": "src-1", "title": "t", "url": "u", "origin_tool": "arxiv"}]\n```'
    sources = parse_sources_payload(payload)
    assert len(sources) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_researcher.py
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Add researcher prompt to `agent/prompts.py`**

Append to `agent/prompts.py`:

```python
RESEARCHER_SYSTEM = """You are the Researcher in a multi-agent academic paper team.

Given a TOPIC and an OUTLINE, gather a balanced source pack of 8–15 high-quality sources \
covering every outline section. Use the available tools (web_search, wikipedia, arxiv, \
document_search if available). Prefer peer-reviewed (arXiv) over Wikipedia for substantive claims.

You MUST end your work by returning ONLY a JSON array (no commentary, no markdown fence) \
of source objects. Each object: \
{"id": "src-N", "title": "...", "authors": ["..."], "year": YYYY|null, "url": "...", \
"snippet": "1-2 sentence quote or summary", "origin_tool": "web_search|wikipedia|arxiv|document_search", \
"covers_sections": ["Introduction", "Background"]}.

Hard limits: ≤ 15 sources, ≤ 12 tool calls total. Dedupe by URL. Number IDs sequentially: src-1, src-2…"""


def get_researcher_prompt(mode: str) -> str:
    from .modes import get_profile
    return RESEARCHER_SYSTEM + "\n\n" + get_profile(mode).researcher_addendum
```

- [ ] **Step 4: Implement `agent/nodes/researcher.py`**

```python
"""Researcher node: wraps a ReAct sub-agent over the 4 source tools."""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from ..prompts import get_researcher_prompt
from ..state import PaperState, Source
from ..tools import build_tools

MAX_SOURCES = 15
MAX_TOOL_CALLS = 12

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_sources_payload(text: str) -> list[Source]:
    """Parse the researcher's final JSON array into validated Source objects.

    Tolerates markdown fences. Dedupes by URL. Caps at MAX_SOURCES.
    """
    cleaned = _FENCE_RE.sub("", text).strip()
    raw = json.loads(cleaned)
    seen_urls: set[str] = set()
    out: list[Source] = []
    for item in raw:
        url = item.get("url") or ""
        if url and url in seen_urls:
            continue
        seen_urls.add(url)
        out.append(Source(**item))
        if len(out) >= MAX_SOURCES:
            break
    return out


def make_researcher_node(llm, vectorstore=None):
    """Returns a node function closed over the LLM and (optional) vectorstore."""
    tools = build_tools(vectorstore=vectorstore)

    def researcher_node(state: PaperState) -> dict:
        outline_str = "\n".join(
            f"- {s.title}: {', '.join(s.bullets) if s.bullets else '(no bullets)'}"
            for s in state["outline"]
        )
        user_msg = f"Topic: {state['topic']}\nOutline:\n{outline_str}"
        sub_agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=get_researcher_prompt(state["mode"]),
        )
        result = sub_agent.invoke({"messages": [HumanMessage(content=user_msg)]})
        final_text = result["messages"][-1].content
        try:
            sources = parse_sources_payload(final_text)
        except (json.JSONDecodeError, ValueError):
            # Retry once with an explicit error
            retry_msg = (
                "Your previous response was not valid JSON. Return ONLY a JSON array "
                "of source objects, no commentary, no fence."
            )
            result = sub_agent.invoke({
                "messages": result["messages"] + [HumanMessage(content=retry_msg)]
            })
            sources = parse_sources_payload(result["messages"][-1].content)
        return {"sources": sources}

    return researcher_node
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_researcher.py
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/nodes/researcher.py agent/prompts.py tests/test_researcher.py
git commit -m "feat(nodes): add researcher node with JSON source-pack parser"
```

---

## Task 8: Implement `nodes/drafter.py` (per-section drafting with citation enforcement)

**Files:**
- Create: `agent/nodes/drafter.py`
- Modify: `agent/prompts.py`
- Create: `tests/test_drafter.py`

The drafter writes one section at a time. After each section is drafted, we run `find_missing_citations` to catch hallucinated `[src-N]` IDs; missing ones are appended to a deferred issues list that gets forwarded to the reviewer.

- [ ] **Step 1: Write failing tests with a fake LLM**

```python
# tests/test_drafter.py
import pytest
from langchain_core.messages import AIMessage


class FakeLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def invoke(self, messages):
        return AIMessage(content=self._responses.pop(0))


def test_drafter_writes_all_sections(sample_state):
    from agent.nodes.drafter import make_drafter_node
    fake = FakeLLM([
        "Introduction body referencing [src-1].",
        "Background body referencing [src-2] and [src-1].",
    ])
    node = make_drafter_node(fake)
    result = node(sample_state)
    assert set(result["draft"].keys()) == {"Introduction", "Background"}
    assert "[src-1]" in result["draft"]["Introduction"]


def test_drafter_flags_hallucinated_citations(sample_state):
    """A draft referencing [src-99] (not in pack) must produce a missing_citation issue."""
    from agent.nodes.drafter import make_drafter_node
    fake = FakeLLM([
        "Intro with bogus citation [src-99].",
        "Background with real [src-2].",
    ])
    node = make_drafter_node(fake)
    result = node(sample_state)
    forced = result.get("forced_review_issues", [])
    kinds = [i.kind for i in forced]
    assert "missing_citation" in kinds
    sections_flagged = [i.section for i in forced if i.kind == "missing_citation"]
    assert "Introduction" in sections_flagged


def test_drafter_revision_pass_uses_review_issues(sample_state):
    """When revision_count == 0 but review.issues exist, drafter must address them."""
    from agent.nodes.drafter import make_drafter_node
    from agent.state import ReviewReport, ReviewIssue
    sample_state["review"] = ReviewReport(
        verdict="revise",
        issues=[ReviewIssue(section="Introduction", kind="weak_argument",
                            suggestion="strengthen thesis")],
    )
    sample_state["draft"] = {"Introduction": "original", "Background": "original"}
    fake = FakeLLM(["Revised intro with [src-1].", "Revised background with [src-2]."])
    node = make_drafter_node(fake)
    result = node(sample_state)
    assert result["revision_count"] == 1
    assert result["draft"]["Introduction"] != "original"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_drafter.py
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Add drafter prompt to `agent/prompts.py`**

Append:

```python
DRAFTER_SYSTEM = """You are the Drafter in a multi-agent academic paper team.

You will be given:
- A SECTION to draft (title, bullets, target_words)
- A SOURCE PACK with IDs like src-1, src-2 — these are the ONLY sources you may cite
- The DRAFT SO FAR (other sections you've already written) for continuity

HARD RULES:
1. Cite inline with [src-N] for every factual claim. Use only IDs from the source pack.
2. NEVER invent a citation. NEVER reference src-N where N is not in the pack.
3. Hit target_words ± 20%. If over, cut. If under, expand.
4. Write in academic register. Topic sentences. Hedged claims. Logical transitions.
5. Output ONLY the section body in Markdown. No section heading, no preamble, no postamble."""


def get_drafter_prompt(mode: str) -> str:
    from .modes import get_profile
    return DRAFTER_SYSTEM + "\n\n" + get_profile(mode).drafter_addendum
```

- [ ] **Step 4: Implement `agent/nodes/drafter.py`**

```python
"""Drafter node: writes the paper section-by-section, enforcing citation grounding."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import get_drafter_prompt
from ..state import PaperState, ReviewIssue
from ..validators import find_missing_citations


def make_drafter_node(llm):
    def drafter_node(state: PaperState) -> dict:
        profile_prompt = get_drafter_prompt(state["mode"])
        source_pack = [s.model_dump() for s in state["sources"]]
        known_ids = {s.id for s in state["sources"]}
        is_revision = (state.get("review") is not None
                       and state["review"].verdict == "revise"
                       and state.get("revision_count", 0) == 0)
        review_issues_by_section: dict[str, list[ReviewIssue]] = {}
        if is_revision:
            for issue in state["review"].issues:
                review_issues_by_section.setdefault(issue.section, []).append(issue)

        new_draft: dict[str, str] = {}
        forced_issues: list[ReviewIssue] = []

        for section in state["outline"]:
            prior = "\n\n".join(
                f"## {t}\n{b}" for t, b in new_draft.items()
            ) or "(none yet)"
            issues_block = ""
            if section.title in review_issues_by_section:
                issues_block = "\nREVIEWER ISSUES TO ADDRESS:\n" + "\n".join(
                    f"- [{i.kind}] {i.suggestion}"
                    for i in review_issues_by_section[section.title]
                )
                prior_section = state.get("draft", {}).get(section.title, "")
                issues_block += f"\n\nPREVIOUS DRAFT OF THIS SECTION:\n{prior_section}"

            user_msg = (
                f"SECTION TO DRAFT:\n"
                f"Title: {section.title}\n"
                f"Bullets: {section.bullets}\n"
                f"Target words: {section.target_words}\n\n"
                f"SOURCE PACK:\n{json.dumps(source_pack, indent=2)}\n\n"
                f"DRAFT SO FAR:\n{prior}"
                f"{issues_block}"
            )
            resp = llm.invoke([
                SystemMessage(content=profile_prompt),
                HumanMessage(content=user_msg),
            ])
            body = resp.content.strip()
            new_draft[section.title] = body
            missing = find_missing_citations(body, known_ids)
            for bad_id in missing:
                forced_issues.append(ReviewIssue(
                    section=section.title,
                    kind="missing_citation",
                    suggestion=f"Citation {bad_id} is not in the source pack. Replace or remove.",
                ))

        update: dict = {"draft": new_draft, "forced_review_issues": forced_issues}
        if is_revision:
            update["revision_count"] = state.get("revision_count", 0) + 1
        return update

    return drafter_node
```

Note: `forced_review_issues` is a transient field consumed by the reviewer node (Task 9). Add it to `PaperState` in `agent/state.py`:

```python
# In agent/state.py, inside PaperState TypedDict, add:
    forced_review_issues: list  # ReviewIssue[] — populated by drafter, consumed by reviewer
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_drafter.py
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/nodes/drafter.py agent/prompts.py agent/state.py tests/test_drafter.py
git commit -m "feat(nodes): add drafter with per-section citation enforcement"
```

---

## Task 9: Implement `nodes/reviewer.py` (LLM-as-judge)

**Files:**
- Create: `agent/nodes/reviewer.py`
- Modify: `agent/prompts.py`
- Create: `tests/test_reviewer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_reviewer.py
import json
from langchain_core.messages import AIMessage


class FakeLLM:
    def __init__(self, response: str):
        self._response = response
    def invoke(self, messages):
        return AIMessage(content=self._response)


def test_reviewer_returns_pass_verdict(sample_state):
    from agent.nodes.reviewer import make_reviewer_node
    sample_state["draft"] = {"Introduction": "good", "Background": "good"}
    sample_state["forced_review_issues"] = []
    fake = FakeLLM(json.dumps({"issues": [], "verdict": "pass"}))
    node = make_reviewer_node(fake)
    result = node(sample_state)
    assert result["review"].verdict == "pass"
    assert result["review"].issues == []


def test_reviewer_includes_forced_issues(sample_state):
    """Drafter-flagged missing_citation issues must end up in the final report."""
    from agent.nodes.reviewer import make_reviewer_node
    from agent.state import ReviewIssue
    sample_state["draft"] = {"Introduction": "weak", "Background": "ok"}
    sample_state["forced_review_issues"] = [
        ReviewIssue(section="Introduction", kind="missing_citation",
                    suggestion="src-99 not in pack")
    ]
    fake = FakeLLM(json.dumps({"issues": [], "verdict": "pass"}))
    node = make_reviewer_node(fake)
    result = node(sample_state)
    assert result["review"].verdict == "revise"  # forced issue upgrades verdict
    assert any(i.kind == "missing_citation" for i in result["review"].issues)


def test_reviewer_combines_llm_and_forced_issues(sample_state):
    from agent.nodes.reviewer import make_reviewer_node
    from agent.state import ReviewIssue
    sample_state["draft"] = {"Introduction": "weak", "Background": "ok"}
    sample_state["forced_review_issues"] = [
        ReviewIssue(section="Introduction", kind="missing_citation", suggestion="x")
    ]
    fake = FakeLLM(json.dumps({
        "issues": [{"section": "Background", "kind": "weak_argument", "suggestion": "y"}],
        "verdict": "revise",
    }))
    node = make_reviewer_node(fake)
    result = node(sample_state)
    assert len(result["review"].issues) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_reviewer.py
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Add reviewer prompt**

Append to `agent/prompts.py`:

```python
REVIEWER_SYSTEM = """You are the Reviewer in a multi-agent academic paper team.

Given an OUTLINE, the full DRAFT (one entry per section), and the SOURCE PACK, \
identify issues that need a second drafting pass.

Respond with ONLY JSON (no markdown fence, no commentary):
{
  "issues": [{"section": "Section Name", "kind": "missing_citation|weak_argument|off_topic|repetition", "suggestion": "concrete fix"}],
  "verdict": "pass" | "revise"
}

Verdict "revise" iff there is at least one substantive issue. Be strict but not pedantic — \
flag real problems (unsupported claims, arguments that don't follow, off-topic content) and \
skip stylistic nits."""
```

- [ ] **Step 4: Implement `agent/nodes/reviewer.py`**

```python
"""Reviewer node: LLM-as-judge producing a structured ReviewReport."""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import REVIEWER_SYSTEM
from ..state import PaperState, ReviewIssue, ReviewReport

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def make_reviewer_node(llm):
    def reviewer_node(state: PaperState) -> dict:
        outline = [s.model_dump() for s in state["outline"]]
        sources = [{"id": s.id, "title": s.title} for s in state["sources"]]
        user_msg = (
            f"OUTLINE: {json.dumps(outline)}\n\n"
            f"SOURCE PACK: {json.dumps(sources)}\n\n"
            f"DRAFT:\n" + "\n\n".join(
                f"## {t}\n{b}" for t, b in state["draft"].items()
            )
        )
        resp = llm.invoke([
            SystemMessage(content=REVIEWER_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        cleaned = _FENCE_RE.sub("", resp.content).strip()
        data = json.loads(cleaned)
        llm_issues = [ReviewIssue(**i) for i in data.get("issues", [])]
        forced = state.get("forced_review_issues", []) or []
        all_issues = forced + llm_issues
        # Forced issues (missing citations) always upgrade verdict to "revise"
        verdict = "revise" if (forced or data.get("verdict") == "revise") else "pass"
        return {"review": ReviewReport(issues=all_issues, verdict=verdict)}

    return reviewer_node
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_reviewer.py
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/nodes/reviewer.py agent/prompts.py tests/test_reviewer.py
git commit -m "feat(nodes): add reviewer (LLM-as-judge) merging forced + LLM issues"
```

---

## Task 10: Implement `nodes/data_analyzer.py` (empirical mode)

**Files:**
- Create: `agent/nodes/data_analyzer.py`
- Modify: `agent/state.py` (add `analysis_results` field)
- Create: `tests/fixtures/sales_data.csv`

This node only runs in empirical mode. It uses `python_repl` (already in `tools.py`) to compute basic descriptives on `user_data` and stashes them in state for the drafter to reference. Integration coverage comes via `verify_pipeline.py` (Task 13). Unit coverage is light because the entire node is one ReAct loop.

- [ ] **Step 1: Add `analysis_results` field to `PaperState`**

In `agent/state.py`, add to the `PaperState` TypedDict:

```python
    analysis_results: dict  # {stat_name: value} — populated by data_analyzer
```

- [ ] **Step 2: Create fixture CSV**

```csv
# tests/fixtures/sales_data.csv
quarter,product,revenue
Q1,A,1200
Q1,B,800
Q2,A,1500
Q2,B,950
Q3,A,1800
Q3,B,1100
```

- [ ] **Step 3: Implement `agent/nodes/data_analyzer.py`**

```python
"""Data analyzer node (empirical mode only): runs python_repl on user_data."""
from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from ..state import PaperState
from ..tools import python_repl

ANALYZER_SYSTEM = """You analyze the user's uploaded data and return summary statistics.

You have one tool: python_repl. Pandas is available. The user's data is described in the message \
(filename + a sample). Read it with pandas, compute relevant descriptives (counts, means, totals, \
trends), and respond with ONLY a JSON object: {"stat_name": value, ...}. Numbers must be JSON-safe \
(int or float, not numpy types — cast with int()/float())."""


def make_data_analyzer_node(llm):
    def data_analyzer_node(state: PaperState) -> dict:
        if state["mode"] != "empirical" or not state.get("user_data"):
            return {"analysis_results": {}}
        # Describe each uploaded doc to the analyzer
        descriptions = []
        for doc in state["user_data"]:
            src = doc.metadata.get("source", "?")
            sample = doc.page_content[:500]
            descriptions.append(f"FILE: {src}\nSAMPLE:\n{sample}")
        user_msg = (
            f"Topic: {state['topic']}\n\n"
            f"Uploaded data:\n\n" + "\n\n---\n\n".join(descriptions)
        )
        sub_agent = create_react_agent(
            model=llm,
            tools=[python_repl],
            prompt=ANALYZER_SYSTEM,
        )
        result = sub_agent.invoke({"messages": [HumanMessage(content=user_msg)]})
        import json, re
        final = result["messages"][-1].content
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", final, flags=re.MULTILINE).strip()
        try:
            stats = json.loads(cleaned)
        except json.JSONDecodeError:
            stats = {"_parse_error": cleaned[:200]}
        return {"analysis_results": stats}

    return data_analyzer_node
```

- [ ] **Step 4: Commit**

```bash
git add agent/nodes/data_analyzer.py agent/state.py tests/fixtures/sales_data.csv
git commit -m "feat(nodes): add data_analyzer for empirical mode"
```

---

## Task 11: Implement `nodes/finalize.py` (Markdown/LaTeX export)

**Files:**
- Create: `agent/nodes/finalize.py`
- Create: `tests/test_finalize.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_finalize.py
def test_finalize_markdown_includes_all_sections(sample_state):
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {
        "Introduction": "intro body [src-1]",
        "Background": "background body [src-2]",
    }
    result = finalize_node(sample_state)
    output = result["final_output"]
    assert "# Transformer attention mechanisms" in output
    assert "## Introduction" in output
    assert "## Background" in output
    assert "intro body" in output


def test_finalize_includes_references_section(sample_state):
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "[src-1] claim.", "Background": "[src-2] more."}
    result = finalize_node(sample_state)
    output = result["final_output"]
    assert "## References" in output
    assert "Attention Is All You Need" in output  # from src-1 in fixture


def test_finalize_orders_references_by_id_appearance(sample_state):
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "[src-3] then [src-1]"}
    result = finalize_node(sample_state)
    refs_section = result["final_output"].split("## References")[1]
    # src-3 cited first should appear before src-1 in references
    assert refs_section.index("Transformer (Wikipedia)") < refs_section.index("Attention Is All You Need")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_finalize.py
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `agent/nodes/finalize.py`**

```python
"""Finalize node: format the draft as a complete Markdown paper with References."""
from __future__ import annotations

import re

from ..state import PaperState

_CITATION_RE = re.compile(r"\[(src-\d+)\]")


def _format_reference(src) -> str:
    parts = []
    if src.authors:
        parts.append(", ".join(src.authors))
    if src.year:
        parts.append(f"({src.year})")
    parts.append(src.title)
    if src.url:
        parts.append(src.url)
    return ". ".join(parts) + "."


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

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_finalize.py
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/nodes/finalize.py tests/test_finalize.py
git commit -m "feat(nodes): add finalize node (Markdown export with References)"
```

---

## Task 12: Wire the StateGraph in `agent/graph.py`

**Files:**
- Modify: `agent/graph.py` (full rewrite)

- [ ] **Step 1: Rewrite `agent/graph.py`**

```python
"""LangGraph state graph for the multi-agent research-paper system."""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .modes import get_profile
from .nodes.data_analyzer import make_data_analyzer_node
from .nodes.drafter import make_drafter_node
from .nodes.finalize import finalize_node
from .nodes.intake import intake_node
from .nodes.researcher import make_researcher_node
from .nodes.reviewer import make_reviewer_node
from .state import PaperState
from .validators import validate_model_name

DEFAULT_MODEL = "gpt-4o-mini"
MAX_REVISIONS = 1


def _should_revise(state: PaperState) -> str:
    """Conditional edge after reviewer: revise once, then advance to finalize."""
    profile = get_profile(state["mode"])
    if profile.skip_reviewer_revision:
        return "finalize"
    review = state.get("review")
    if not review or review.verdict == "pass":
        return "finalize"
    if state.get("revision_count", 0) >= MAX_REVISIONS:
        return "finalize"
    return "drafter"


def _after_intake(state: PaperState) -> str:
    """Empirical mode goes through data_analyzer; others skip it."""
    return "data_analyzer" if state["mode"] == "empirical" else "researcher"


def build_graph(
    model_name: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    vectorstore=None,
    checkpointer: MemorySaver | None = None,
):
    validate_model_name(model_name)
    llm = ChatOpenAI(model=model_name, temperature=temperature)

    builder = StateGraph(PaperState)
    builder.add_node("intake", lambda s: intake_node(s, llm))
    builder.add_node("data_analyzer", make_data_analyzer_node(llm))
    builder.add_node("researcher", make_researcher_node(llm, vectorstore=vectorstore))
    builder.add_node("drafter", make_drafter_node(llm))
    builder.add_node("reviewer", make_reviewer_node(llm))
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "intake")
    builder.add_conditional_edges("intake", _after_intake,
                                  {"data_analyzer": "data_analyzer", "researcher": "researcher"})
    builder.add_edge("data_analyzer", "researcher")
    builder.add_edge("researcher", "drafter")
    builder.add_edge("drafter", "reviewer")
    builder.add_conditional_edges("reviewer", _should_revise,
                                  {"drafter": "drafter", "finalize": "finalize"})
    builder.add_edge("finalize", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["researcher", "drafter", "finalize"],
    )


# Back-compat shim for the old single-agent API. Will be removed after app.py migrates.
build_agent = build_graph
```

- [ ] **Step 2: Add minimal smoke test for graph construction**

```python
# tests/test_graph_build.py (NEW)
def test_graph_builds_without_api_key(monkeypatch):
    """Graph construction must not require an API call — only happens on first invoke."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-construction-only")
    from agent.graph import build_graph
    g = build_graph(model_name="gpt-4o-mini")
    # Confirm interrupts are wired
    assert hasattr(g, "get_state")


def test_graph_rejects_invalid_model():
    import pytest
    with pytest.raises(ValueError, match="not in allowlist"):
        from agent.graph import build_graph
        build_graph(model_name="gpt-5.4-mini")
```

- [ ] **Step 3: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_graph_build.py
```

Expected: both tests pass.

- [ ] **Step 4: Run the full unit-test suite to confirm nothing regressed**

```bash
.venv/Scripts/python -m pytest
```

Expected: all tests pass (now ~30+ tests).

- [ ] **Step 5: Commit**

```bash
git add agent/graph.py tests/test_graph_build.py
git commit -m "feat(agent): wire StateGraph with conditional edges and 3 interrupts"
```

---

## Task 13: Implement `verify_pipeline.py` (integration harness, replaces `verify.py`)

**Files:**
- Create: `verify_pipeline.py`
- Delete: `verify.py`

This is the same style as today's `verify.py` (no pytest, prints PASS/FAIL, exits non-zero on failure). It exercises the full graph end-to-end against the real OpenAI API. Gated by `OPENAI_API_KEY`.

- [ ] **Step 1: Create `verify_pipeline.py`**

```python
"""End-to-end integration harness for the multi-agent paper graph.

Run from project root with the venv active and OPENAI_API_KEY set:
    .venv/Scripts/python verify_pipeline.py

Exits non-zero on any failure. Skips cleanly if OPENAI_API_KEY is missing.
"""
from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    print("SKIP: OPENAI_API_KEY not set")
    sys.exit(0)

from langchain_core.documents import Document
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import DEFAULT_MODEL, build_graph
from agent.state import TokenUsage
from agent.validators import find_missing_citations

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def header(title: str) -> None:
    print(f"\n{'=' * 64}\n  {title}\n{'=' * 64}", flush=True)


def ok(name: str, detail: str = "") -> None:
    print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""), flush=True)
    PASSED.append(name)


def ko(name: str, detail: str) -> None:
    print(f"  [FAIL] {name} — {detail}", flush=True)
    FAILED.append((name, detail))


def run_to_completion(graph, initial: dict, thread_id: str) -> dict:
    """Run graph past all interrupts by auto-approving each checkpoint."""
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(initial, config=config)
    while True:
        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values
        # Auto-approve: resume with no edits
        graph.invoke(None, config=config)


# ============================================================
header("CHECK 1: Survey mode end-to-end")
# ============================================================
graph = build_graph(model_name=DEFAULT_MODEL)
t0 = time.time()
state = run_to_completion(graph, {
    "topic": "Transformer attention mechanisms",
    "mode": "survey",
    "user_data": [],
    "token_usage": TokenUsage(),
    "messages": [],
}, thread_id="survey-1")
elapsed = time.time() - t0
print(f"  Completed in {elapsed:.1f}s")

if len(state.get("sources", [])) >= 6:
    ok("Survey gathered ≥6 sources", f"got {len(state['sources'])}")
else:
    ko("Survey source count", f"only got {len(state.get('sources', []))}")

if state.get("final_output", "").startswith("# "):
    ok("Survey produced final output")
else:
    ko("Survey final output", "missing or malformed")

known_ids = {s.id for s in state.get("sources", [])}
all_draft = " ".join(state.get("draft", {}).values())
missing = find_missing_citations(all_draft, known_ids)
if not missing:
    ok("Survey citations all resolve")
else:
    ko("Survey citations", f"hallucinated: {missing}")


# ============================================================
header("CHECK 2: Empirical mode runs data_analyzer")
# ============================================================
csv_text = open("tests/fixtures/sales_data.csv").read()
graph = build_graph(model_name=DEFAULT_MODEL)
state = run_to_completion(graph, {
    "topic": "Q3 sales trends",
    "mode": "empirical",
    "user_data": [Document(page_content=csv_text, metadata={"source": "sales_data.csv"})],
    "token_usage": TokenUsage(),
    "messages": [],
}, thread_id="empirical-1")

if state.get("analysis_results"):
    ok("Empirical analyzer ran", f"stats={list(state['analysis_results'].keys())[:3]}")
else:
    ko("Empirical analyzer", "no analysis_results in state")


# ============================================================
header("CHECK 3: Term mode skips reviewer revision")
# ============================================================
graph = build_graph(model_name=DEFAULT_MODEL)
state = run_to_completion(graph, {
    "topic": "Why universal healthcare matters",
    "mode": "term",
    "user_data": [],
    "token_usage": TokenUsage(),
    "messages": [],
}, thread_id="term-1")

if state.get("revision_count", 0) == 0:
    ok("Term mode skipped revision loop")
else:
    ko("Term mode", f"unexpected revision_count={state.get('revision_count')}")


# ============================================================
header("CHECK 4: Resume across simulated browser close")
# ============================================================
shared_checkpointer = MemorySaver()
g1 = build_graph(model_name=DEFAULT_MODEL, checkpointer=shared_checkpointer)
g1.invoke({
    "topic": "X", "mode": "term", "user_data": [],
    "token_usage": TokenUsage(), "messages": [],
}, config={"configurable": {"thread_id": "resume-1"}})
snapshot1 = g1.get_state({"configurable": {"thread_id": "resume-1"}})

# "Restart" by building a new graph object with the same checkpointer
g2 = build_graph(model_name=DEFAULT_MODEL, checkpointer=shared_checkpointer)
snapshot2 = g2.get_state({"configurable": {"thread_id": "resume-1"}})

if snapshot2.values.get("topic") == "X" and snapshot1.next == snapshot2.next:
    ok("Resume across graph rebuild", f"resumed at node={snapshot2.next}")
else:
    ko("Resume", f"state lost: snap1={snapshot1.values.get('topic')} snap2={snapshot2.values.get('topic')}")


# ============================================================
header("SUMMARY")
# ============================================================
print(f"  Passed: {len(PASSED)}")
print(f"  Failed: {len(FAILED)}")
if FAILED:
    print("\n  Failures:")
    for name, msg in FAILED:
        print(f"    - {name}: {msg}")
    sys.exit(1)
print("\n  All integration checks passed.")
sys.exit(0)
```

- [ ] **Step 2: Run it once locally to confirm it works**

```bash
.venv/Scripts/python verify_pipeline.py
```

Expected: all 4 checks PASS. If CHECK 1 takes more than ~3 minutes, the agent is doing something pathological — investigate before continuing.

- [ ] **Step 3: Delete the old verify.py**

```bash
rm verify.py
```

- [ ] **Step 4: Commit**

```bash
git add verify_pipeline.py
git rm verify.py
git commit -m "test: replace verify.py with verify_pipeline.py (end-to-end graph harness)"
```

---

## Task 14: Implement golden outline snapshot test

**Files:**
- Create: `tests/golden/__init__.py`
- Create: `tests/golden/test_outline_snapshot.py`
- Create: `tests/golden/survey_attention_outline.json` (generated on first run)

This test detects unintentional prompt regressions in the intake node. It asserts the outline *shape* (section titles, count) — not the prose — against a committed snapshot.

- [ ] **Step 1: Create `tests/golden/__init__.py`** (empty file)

- [ ] **Step 2: Write the snapshot test**

```python
# tests/golden/test_outline_snapshot.py
"""Golden test: outline shape for a fixed (topic, mode) at temp=0.

On first run with an OPENAI_API_KEY set, writes the snapshot.
On subsequent runs, asserts the outline shape matches.
Skips cleanly when OPENAI_API_KEY is missing."""
import json
import os
from pathlib import Path

import pytest

SNAPSHOT_PATH = Path(__file__).parent / "survey_attention_outline.json"


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_survey_outline_shape_stable():
    from langchain_openai import ChatOpenAI
    from agent.nodes.intake import intake_node

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    result = intake_node(
        {"topic": "Transformer attention mechanisms", "mode": "survey"},
        llm,
    )
    shape = {
        "section_count": len(result["outline"]),
        "titles": [s.title for s in result["outline"]],
        "target_words": [s.target_words for s in result["outline"]],
    }
    if not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.write_text(json.dumps(shape, indent=2))
        pytest.skip(f"Wrote initial snapshot to {SNAPSHOT_PATH}; rerun to assert")
    expected = json.loads(SNAPSHOT_PATH.read_text())
    assert shape == expected, (
        f"Outline shape drifted.\nExpected: {expected}\nGot: {shape}\n"
        f"If this drift is intentional, delete {SNAPSHOT_PATH} and rerun."
    )
```

- [ ] **Step 3: Run once to generate the snapshot**

```bash
.venv/Scripts/python -m pytest tests/golden/test_outline_snapshot.py -v
```

Expected: SKIPPED with "Wrote initial snapshot". File `tests/golden/survey_attention_outline.json` now exists.

- [ ] **Step 4: Run again to assert it matches**

```bash
.venv/Scripts/python -m pytest tests/golden/test_outline_snapshot.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/golden/
git commit -m "test: add golden snapshot for survey outline shape"
```

---

## Task 15: Rewrite `app.py` with checkpoint card UI

**Files:**
- Modify: `app.py` (full rewrite)

This is the largest single-file change. The structure:
1. Session state: `thread_id`, `checkpointer`, `vectorstore`, `mode`, `pending_checkpoint`.
2. Sidebar: API key status, mode selector, document uploader (unchanged from today), clear button.
3. Main panel: chat-style trace of the run + checkpoint cards rendered when paused.

- [ ] **Step 1: Rewrite `app.py`**

```python
"""Streamlit UI for the multi-agent research-paper system."""
import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import DEFAULT_MODEL, build_graph
from agent.state import Section, Source, TokenUsage

load_dotenv()

st.set_page_config(page_title="Research Paper Agent", page_icon="📑", layout="wide")

# --- Session state init ---
defaults = {
    "thread_id": str(uuid.uuid4()),
    "checkpointer": MemorySaver(),
    "vectorstore": None,
    "indexed_files": [],
    "mode": "survey",
    "pending_checkpoint": None,
    "run_started": False,
    "trace": [],   # list of {kind, content} for the chat-style render
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Settings")

    if os.getenv("OPENAI_API_KEY"):
        st.success("OpenAI API key loaded")
    else:
        st.error("OPENAI_API_KEY missing — set it in .env")

    st.session_state.mode = st.selectbox(
        "Paper mode",
        ["survey", "empirical", "term"],
        index=["survey", "empirical", "term"].index(st.session_state.mode),
        help=(
            "**survey**: literature review · **empirical**: built around your data · "
            "**term**: standard essay (no review loop)"
        ),
    )

    if st.button("🗑️ Start over", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v if not callable(v) else v
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.checkpointer = MemorySaver()
        st.rerun()

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
            st.success(f"Indexed {len(summary)} file(s).")

    if st.session_state.indexed_files:
        for name, n in st.session_state.indexed_files:
            st.caption(f"• `{name}` — {n} chunks")

    st.divider()
    st.caption(f"Thread: `{st.session_state.thread_id[:8]}…`")


# --- Main panel ---
st.title("📑 Research Paper Agent")
st.caption("Multi-agent: researcher → drafter → reviewer. You approve at each checkpoint.")


def get_graph():
    return build_graph(
        model_name=DEFAULT_MODEL,
        vectorstore=st.session_state.vectorstore,
        checkpointer=st.session_state.checkpointer,
    )


def config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def render_trace():
    for entry in st.session_state.trace:
        if entry["kind"] == "user":
            with st.chat_message("user"):
                st.markdown(entry["content"])
        elif entry["kind"] == "node":
            with st.chat_message("assistant"):
                st.markdown(f"**✓ {entry['node']}** complete")
                if entry.get("detail"):
                    with st.expander("details"):
                        st.json(entry["detail"])
        elif entry["kind"] == "final":
            with st.chat_message("assistant"):
                st.markdown(entry["content"])


def stream_until_interrupt(initial_input=None):
    graph = get_graph()
    for event in graph.stream(initial_input, config=config(), stream_mode="updates"):
        for node, payload in event.items():
            st.session_state.trace.append({
                "kind": "node", "node": node,
                "detail": {k: str(v)[:200] for k, v in (payload or {}).items()},
            })
    snapshot = graph.get_state(config())
    if snapshot.next:
        st.session_state.pending_checkpoint = snapshot.next[0]
    else:
        st.session_state.pending_checkpoint = None


def render_checkpoint_card():
    graph = get_graph()
    snapshot = graph.get_state(config())
    cp = st.session_state.pending_checkpoint

    if cp == "researcher":
        st.subheader("Checkpoint 1: Confirm outline")
        outline = snapshot.values.get("outline", [])
        edited_titles = []
        edited_bullets = []
        edited_words = []
        for i, sec in enumerate(outline):
            with st.expander(f"§ {sec.title}", expanded=True):
                edited_titles.append(st.text_input("Title", sec.title, key=f"t{i}"))
                edited_bullets.append(st.text_area("Bullets (one per line)",
                                                    "\n".join(sec.bullets), key=f"b{i}"))
                edited_words.append(st.number_input("Target words", value=sec.target_words,
                                                     step=50, key=f"w{i}"))
        col1, col2 = st.columns(2)
        if col1.button("✅ Approve outline → start research", type="primary",
                       use_container_width=True):
            new_outline = [
                Section(title=t, bullets=[b for b in bs.split("\n") if b.strip()],
                        target_words=int(w))
                for t, bs, w in zip(edited_titles, edited_bullets, edited_words)
            ]
            graph.update_state(config(), {"outline": new_outline})
            st.session_state.pending_checkpoint = None
            with st.spinner("Researching…"):
                stream_until_interrupt(None)
            st.rerun()
        if col2.button("❌ Cancel paper", use_container_width=True):
            st.session_state.pending_checkpoint = None
            st.session_state.run_started = False
            st.rerun()

    elif cp == "drafter":
        st.subheader("Checkpoint 2: Approve source pack")
        sources = snapshot.values.get("sources", [])
        keep = []
        for src in sources:
            label = f"**{src.id}** — {src.title} ({src.origin_tool})"
            if st.checkbox(label, value=True, key=f"src{src.id}"):
                keep.append(src)
            if src.url:
                st.caption(src.url)
        if st.button(f"✅ Draft with {len(keep)} sources", type="primary",
                     use_container_width=True):
            graph.update_state(config(), {"sources": keep})
            st.session_state.pending_checkpoint = None
            with st.spinner("Drafting…"):
                stream_until_interrupt(None)
            st.rerun()

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


# --- Main flow ---
render_trace()

if st.session_state.pending_checkpoint:
    render_checkpoint_card()
elif st.session_state.run_started:
    # Run completed
    graph = get_graph()
    snapshot = graph.get_state(config())
    final = snapshot.values.get("final_output")
    if final:
        st.success("📑 Paper complete")
        st.download_button("⬇️ Download Markdown", final,
                           file_name="paper.md", mime="text/markdown")
        with st.expander("Preview", expanded=True):
            st.markdown(final)
else:
    topic = st.chat_input("Paper topic (e.g. 'Transformer attention mechanisms')")
    if topic:
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Set OPENAI_API_KEY in .env first.")
            st.stop()
        st.session_state.trace.append({"kind": "user", "content": topic})
        st.session_state.run_started = True
        with st.spinner("Generating outline…"):
            user_data = []
            if st.session_state.vectorstore is not None and st.session_state.mode == "empirical":
                # Pull docs from vectorstore for the empirical analyzer
                user_data = [
                    d for d in st.session_state.vectorstore.docstore._dict.values()
                ][:10]
            stream_until_interrupt({
                "topic": topic,
                "mode": st.session_state.mode,
                "user_data": user_data,
                "token_usage": TokenUsage(),
                "messages": [],
            })
        st.rerun()
```

- [ ] **Step 2: Smoke-test in a browser**

```bash
.venv/Scripts/streamlit run app.py
```

Walk through each mode end-to-end:
- **survey**: enter a topic, approve outline, approve sources, approve draft, download
- **term**: same flow, confirm reviewer revision is skipped
- **empirical**: upload `tests/fixtures/sales_data.csv`, set mode to empirical, run

Confirm: each checkpoint card renders, editing the outline/sources persists, download produces a real `.md`, "Start over" wipes state.

If the UI is broken or unusable, **stop and fix** before continuing to the next task. If you can't reach a working UI, say so explicitly rather than committing a broken UI.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(ui): rewrite Streamlit app with checkpoint cards for 3 interrupts"
```

---

## Task 16: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite the README to reflect the new design**

Replace the entire README content with:

```markdown
# 📑 Research Paper Agent

Multi-agent academic writing assistant: a LangGraph state machine of three specialists \
(Researcher → Drafter → Reviewer) that produces grounded, cited research papers in three modes.

## Modes
- **survey** — literature review / synthesis paper (full review loop)
- **empirical** — built around your uploaded data (CSV/PDF), adds a data-analyzer step
- **term** — standard essay (single drafter pass, no review loop)

At each of three checkpoints (outline → sources → draft) the human approves or edits \
before the graph continues. State persists for the lifetime of the Streamlit server \
via in-memory `MemorySaver` (no on-disk persistence by design).

## Stack
- **LLM**: OpenAI (`gpt-4o-mini` by default, configurable)
- **Orchestration**: LangGraph `StateGraph` with `interrupt_before` checkpoints
- **UI**: Streamlit, checkpoint-card flow
- **Tools**: DuckDuckGo, Wikipedia, arXiv, Python REPL, document search (FAISS + FastEmbed)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your OpenAI key.

## Run

```bash
streamlit run app.py
```

## Test

Unit tests (no API key needed):
```bash
pytest
```

End-to-end integration (real OpenAI calls, takes ~2-5 min):
```bash
python verify_pipeline.py
```

Run `verify_pipeline.py` before any PR that touches `agent/graph.py` or any node.

## Project layout

```
agent/
├── state.py            # PaperState TypedDict + Pydantic models
├── modes.py            # survey/empirical/term profiles
├── validators.py       # citations, budget tracker, model allowlist
├── graph.py            # StateGraph build with 3 interrupts
├── nodes/
│   ├── intake.py
│   ├── researcher.py
│   ├── drafter.py
│   ├── data_analyzer.py
│   ├── reviewer.py
│   └── finalize.py
├── tools.py            # 5 source tools (unchanged from v1)
├── prompts.py          # per-agent + per-mode prompts
└── rag.py              # PDF/TXT → FAISS (unchanged from v1)

tests/                  # unit tests, no API calls
verify_pipeline.py      # integration harness, requires OPENAI_API_KEY
app.py                  # Streamlit UI
```

## Privacy

Uploaded documents stay in process memory (FAISS in `st.session_state`). \
Nothing is persisted to disk. Restarting the Streamlit server clears all state.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for multi-agent system"
```

---

## Task 17: Run the full suite and verify nothing regressed

- [ ] **Step 1: Run unit tests**

```bash
.venv/Scripts/python -m pytest -v
```

Expected: all tests pass. Count tests — should be ~35-40 across all `tests/test_*.py` and `tests/golden/test_outline_snapshot.py`.

- [ ] **Step 2: Run integration tests**

```bash
.venv/Scripts/python verify_pipeline.py
```

Expected: all 4 integration checks PASS. Total runtime under 5 minutes.

- [ ] **Step 3: Smoke-test the UI one more time**

```bash
.venv/Scripts/streamlit run app.py
```

Walk one paper through end-to-end in each mode. Confirm download produces a valid `.md` file.

- [ ] **Step 4: If everything passes, this is the end of the plan**

Final commit is unnecessary unless tests revealed bugs to fix. The project now has:
- 3-agent LangGraph state machine
- 3 modes (survey / empirical / term)
- 3 checkpoint interrupts + terminal download
- ~35 unit tests, 4 integration checks, 1 golden snapshot
- Model-name validation, citation hallucination detection, budget tracking

---

## Self-review notes

After writing this plan I checked it against the spec and found these items to fix:

1. **`forced_review_issues` field**: introduced in Task 8 but not declared in `state.py` (Task 3). Fixed inline in Task 8 Step 4 with explicit instruction to add the field.
2. **`analysis_results` field**: same issue for empirical mode. Fixed inline in Task 10 Step 1.
3. **Budget tracker integration**: spec §7 says token usage is tracked across the run. The validator exists (Task 4) and `TokenUsage` is in state, but no node currently writes to it. **Known gap** — actual token accounting requires hooking into the LLM callbacks, which is meaningful work; deferred as a v1.1 improvement. UI shows `token_usage` from state if present (zeros for now). Flag this to the user before starting Task 15 so the UI doesn't promise a feature that does nothing.
4. **`tenacity` retry**: added to requirements (Task 1) but not actually wired into any node. **Known gap** — wrap `llm.invoke()` in retry inside the researcher/drafter/reviewer factories. Cheapest place to add this is a small helper in `validators.py`. Suggest a follow-up task after Task 17 if integration runs flake on rate limits.
5. **`document_search` and CSV**: `app.py` (Task 15) passes `user_data` to empirical mode by pulling docs from the vectorstore. But the `rag.py` uploader doesn't handle CSV today. Either restrict empirical to PDF/TXT or extend `rag.py` to handle CSV. Plan currently restricts upload UI to PDF/TXT/CSV but `rag.py` will skip CSV — Task 15 caveats this. Add Task 10.5 if CSV support is required for v1.

The three gaps above (budget hooks, retry wiring, CSV ingest) are explicitly out of scope of this plan — call them out to the user before execution so expectations match what ships.
