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
