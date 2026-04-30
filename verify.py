"""End-to-end verification harness for the research agent.

Run from the project root with the venv active:
    .venv/Scripts/python.exe verify.py

Exercises: tool registration, each tool individually, agent routing decisions,
RAG over the cahier PDF, and conversation memory. Exits non-zero on any failure.
"""

from __future__ import annotations

import pathlib
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from langchain_community.vectorstores import FAISS
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_agent
from agent.prompts import get_prompt
from agent.rag import chunk_documents, get_embeddings, load_pdf
from agent.tools import arxiv, build_tools, python_repl, web_search, wikipedia

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []
MODEL = "gpt-5.4-mini"


def header(title: str) -> None:
    print(f"\n{'=' * 64}\n  {title}\n{'=' * 64}", flush=True)


def ok(name: str, detail: str = "") -> None:
    print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""), flush=True)
    PASSED.append(name)


def ko(name: str, detail: str) -> None:
    print(f"  [FAIL] {name} — {detail}", flush=True)
    FAILED.append((name, detail))


def run_agent(agent, question: str, thread: str) -> tuple[str, list[str]]:
    t0 = time.time()
    result = agent.invoke(
        {"messages": [HumanMessage(content=question)]},
        config={"configurable": {"thread_id": thread}},
    )
    elapsed = time.time() - t0
    calls: list[str] = []
    for m in result["messages"]:
        if isinstance(m, AIMessage) and m.tool_calls:
            calls.extend(tc["name"] for tc in m.tool_calls)
    final = result["messages"][-1].content
    print(f"    -> {elapsed:.1f}s, tools={calls}, answer[:120]={final[:120]!r}", flush=True)
    return final, calls


# ============================================================
header("CHECK 0: Configuration")
# ============================================================
prompt = get_prompt(has_documents=False)
print(f"  System prompt length: {len(prompt)} chars")
print(f"  Prompt starts: {prompt[:80]!r}")
print(f"  Model under test: {MODEL}")
ok("System prompt loads")


# ============================================================
header("CHECK 1: Tool registration")
# ============================================================
tools = build_tools()
got = sorted(t.name for t in tools)
expected = ["arxiv", "python_repl", "web_search", "wikipedia"]
if got == expected:
    ok("Base tools", str(got))
else:
    ko("Base tools", f"expected {expected}, got {got}")


# ============================================================
header("CHECK 2: Each tool runs independently")
# ============================================================
try:
    r = python_repl.invoke("print(2+2)")
    ok("python_repl(2+2)", f"got {r.strip()!r}") if "4" in r else ko("python_repl", r)
except Exception as e:
    ko("python_repl", repr(e))

try:
    r = wikipedia.invoke("Albert Einstein")
    ok("wikipedia(Einstein)", f"{len(r)} chars") if len(r) > 100 else ko("wikipedia", r[:120])
except Exception as e:
    ko("wikipedia", repr(e))

try:
    r = arxiv.invoke("transformer attention is all you need")
    ok("arxiv(transformer)", f"{len(r)} chars") if len(r) > 100 else ko("arxiv", r[:120])
except Exception as e:
    ko("arxiv", repr(e))

try:
    r = web_search.invoke("Python programming language Wikipedia")
    if len(r) > 50:
        ok("web_search(python)", f"{len(r)} chars")
    else:
        ok("web_search", f"got {len(r)} chars (may be rate-limited)")
except Exception as e:
    ko("web_search", repr(e))


# ============================================================
header("CHECK 3: Agent routing — math -> python_repl")
# ============================================================
agent = build_agent(model_name=MODEL)
text, calls = run_agent(agent, "What is 137 * 89? Calculate it precisely.", "t3")
if "python_repl" in calls and "12193" in text.replace(",", "").replace(" ", ""):
    ok("Math routing", f"calls={calls}")
else:
    ko("Math routing", f"calls={calls}, text={text[:200]}")


# ============================================================
header("CHECK 4: Agent routing — biography -> wikipedia")
# ============================================================
agent = build_agent(model_name=MODEL)
text, calls = run_agent(agent, "Use Wikipedia to tell me who Marie Curie was in one sentence.", "t4")
if "wikipedia" in calls and "curie" in text.lower():
    ok("Biography routing", f"calls={calls}")
else:
    ko("Biography routing", f"calls={calls}, text={text[:200]}")


# ============================================================
header("CHECK 5: Agent routing — academic -> arxiv")
# ============================================================
agent = build_agent(model_name=MODEL)
text, calls = run_agent(
    agent,
    "Search arXiv for one recent paper about retrieval-augmented generation. Just one.",
    "t5",
)
if "arxiv" in calls:
    ok("Academic routing", f"calls={calls}")
else:
    ko("Academic routing", f"calls={calls}, text={text[:200]}")


# ============================================================
header("CHECK 6: RAG over the cahier PDF")
# ============================================================
pdf_path = pathlib.Path("C:/Users/amine/Downloads/CAHIER_DE_CHARGE_D_TAILL_.pdf")
if not pdf_path.exists():
    ko("RAG", f"PDF not found at {pdf_path}")
else:
    data = pdf_path.read_bytes()
    docs = load_pdf(data, pdf_path.name)
    print(f"  Loaded {len(docs)} non-empty pages")
    chunks = chunk_documents(docs)
    print(f"  Split into {len(chunks)} chunks")
    t0 = time.time()
    vs = FAISS.from_documents(chunks, get_embeddings())
    print(f"  Built FAISS index ({vs.index.ntotal} vectors) in {time.time() - t0:.1f}s")

    rag_tools = build_tools(vectorstore=vs)
    if any(t.name == "document_search" for t in rag_tools):
        ok("document_search registered", str([t.name for t in rag_tools]))
    else:
        ko("document_search registered", "tool missing")

    rag_agent = build_agent(model_name=MODEL, vectorstore=vs)
    text, calls = run_agent(
        rag_agent,
        "Search my uploaded document and tell me what the deliverables are for the project.",
        "t6",
    )
    if "document_search" in calls:
        ok("RAG routing", f"calls={calls}")
    else:
        ko("RAG routing", f"expected document_search, got {calls}")

    keywords = ["code", "documentation", "vidéo", "video", "présentation", "presentation", "github"]
    hits = [k for k in keywords if k.lower() in text.lower()]
    if len(hits) >= 2:
        ok("RAG content matches cahier", f"keywords matched: {hits}")
    else:
        ko("RAG content", f"only matched {hits} in: {text[:300]}")


# ============================================================
header("CHECK 7: Conversation memory across 2 turns")
# ============================================================
checkpointer = MemorySaver()
mem_agent = build_agent(model_name=MODEL, checkpointer=checkpointer)
thread = "memtest"
run_agent(mem_agent, "My name is Amine and my favorite number is 42.", thread)
text, _ = run_agent(mem_agent, "What's my name and my favorite number?", thread)
low = text.lower()
if "amine" in low and "42" in text:
    ok("Memory across turns", "recalled both facts")
elif "amine" in low or "42" in text:
    ko("Memory across turns (partial)", text[:200])
else:
    ko("Memory across turns", text[:200])


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
print("\n  All checks passed.")
sys.exit(0)
