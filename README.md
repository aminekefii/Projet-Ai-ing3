# 🎓 University Writing Assistant

Source-grounded writing assistant for university students, built on top of
a multi-tool ReAct agent and augmented with a RAG pipeline over the student's
own readings, notes, and primary sources.

The agent helps plan, research, draft, cite, and revise university-level
articles — essays, term papers, literature reviews, research articles,
dissertation chapters. It picks the right tool for each sub-question,
cross-checks sources, and replies in clean academic Markdown with inline
citations and a Sources / References section.

## Stack

- **LLM**: [OpenAI](https://openai.com) — `gpt-4o-mini` (configurable)
- **Agent core**: [LangGraph](https://langchain-ai.github.io/langgraph/) ReAct agent + `MemorySaver` for conversation memory
- **UI**: [Streamlit](https://streamlit.io) chat with live tool-call visualization + sidebar document uploader
- **Embeddings**: [FastEmbed](https://github.com/qdrant/fastembed) (`BAAI/bge-small-en-v1.5`, ONNX, ~33 MB, runs on CPU)
- **Vector store**: [FAISS](https://github.com/facebookresearch/faiss) in-memory
- **Tools** (5 — last one appears only when readings are loaded):
  - `web_search` — DuckDuckGo (current sources, statistics, news, open-access papers)
  - `wikipedia` — background, definitions, biographies (starting point, not final source)
  - `arxiv` — peer-reviewed and pre-print research
  - `python_repl` — math, statistics, unit conversion that lands in the article
  - `document_search` — semantic search over the student's uploaded readings (PDF/TXT)

## Setup

1. **Python 3.11+ recommended** (3.13 tested).
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # macOS/Linux
   pip install -r requirements.txt
   ```

3. Get an OpenAI API key at <https://platform.openai.com/api-keys>.
4. Copy `.env.example` to `.env` and paste your key:

   ```
   OPENAI_API_KEY=sk-...
   ```

5. Run the app:

   ```bash
   streamlit run app.py
   ```

The app opens at <http://localhost:8501>. The first time you index a document,
FastEmbed downloads the embedding model (~33 MB).

## Project layout

```
ProjetAI/
├── app.py                  # Streamlit chat UI + sidebar uploader + live tool-call streaming
├── agent/
│   ├── __init__.py
│   ├── graph.py            # LangGraph ReAct agent (OpenAI + tools + checkpointer)
│   ├── tools.py            # Tool definitions (5 tools, error-safe)
│   ├── prompts.py          # System prompts (base + docs-aware variant)
│   └── rag.py              # PDF/TXT loading, chunking, embedding, FAISS indexing
├── requirements.txt
├── .env.example
└── .gitignore
```

## How it works

### Agent loop

1. The student submits a request in the Streamlit chat (a topic, an outline ask, a draft request, a revision ask, a citation question…).
2. The LangGraph ReAct agent receives the message + academic-writing system prompt + tool schemas.
3. The OpenAI LLM **plans** a step: either call a tool to source a claim or produce a final answer.
4. If a tool is called, its result is fed back into the loop — the LLM **reasons** over it and decides the next step (cross-check with another source, draft a paragraph, propose an outline, etc.).
5. The loop continues until the LLM produces a final answer with inline citations and a Sources / References section.
6. Each tool call and each tool result is streamed live to the UI as collapsible status boxes, so the student can see exactly where each claim came from.

Conversation memory is preserved across turns via `MemorySaver` keyed by a per-session `thread_id` — useful when iterating on the same paper across many turns (outline → draft section 1 → revise → draft section 2…).

### Readings RAG (sidebar uploader)

1. The student uploads one or more PDF/TXT files (course readings, lecture notes, primary sources).
2. **Loading** — `pypdf` extracts text page by page (PDF) or decodes UTF-8 (TXT). Empty pages are skipped.
3. **Chunking** — `RecursiveCharacterTextSplitter` splits on paragraph/sentence boundaries, then on words, with `chunk_size=800` and `chunk_overlap=120` (advanced overlap-based chunking).
4. **Embedding** — Each chunk is encoded with FastEmbed's `bge-small-en-v1.5` (384-dim, ONNX, CPU).
5. **Indexing** — Chunks + vectors stored in an in-memory FAISS index, kept in `st.session_state.vectorstore`.
6. **Retrieval** — When the agent calls `document_search(query)`, the query is embedded and the top-4 most similar chunks are returned with `source` and `page` metadata for citation.

When at least one document is indexed, the agent's system prompt is augmented with an addendum instructing it to consult `document_search` first for any claim that the assigned readings likely cover, and to cite the uploaded sources under "Course materials" in the Sources / References section.

## Resilience

Every tool wraps its underlying client in a `try/except` and returns errors as
strings to the agent. A single tool failure (rate-limit, malformed response,
network blip) does not abort the run — the agent reads the error message and
either retries with a different query or falls back to another tool.
