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
    builder.add_node("drafter", make_drafter_node(llm, vectorstore=vectorstore))
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
