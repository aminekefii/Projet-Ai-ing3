"""Data analyzer node (empirical mode only): runs python_repl on user_data."""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from ..state import PaperState
from ..tools import python_repl

ANALYZER_SYSTEM = """You analyze the user's uploaded data and return summary statistics.

You have one tool: python_repl. Pandas is available. The user's data is described in the message \
(filename + a sample). Read it with pandas, compute relevant descriptives (counts, means, totals, \
trends), and respond with ONLY a JSON object: {"stat_name": value, ...}. Numbers must be JSON-safe \
(int or float, not numpy types — cast with int()/float())."""


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def make_data_analyzer_node(llm):
    def data_analyzer_node(state: PaperState) -> dict:
        if state["mode"] != "empirical" or not state.get("user_data"):
            return {"analysis_results": {}}
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
        final = result["messages"][-1].content
        cleaned = _FENCE_RE.sub("", final).strip()
        try:
            stats = json.loads(cleaned)
        except json.JSONDecodeError:
            stats = {"_parse_error": cleaned[:200]}
        return {"analysis_results": stats}

    return data_analyzer_node
