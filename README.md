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
