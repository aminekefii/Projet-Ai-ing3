"""Researcher node: wraps a ReAct sub-agent over the 4 source tools."""
from __future__ import annotations

import json
import re

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from ..prompts import get_researcher_prompt
from ..state import PaperState, Source
from ..tools import build_tools

MAX_SOURCES = 15
MAX_TOOL_CALLS = 12

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class _ToolTraceHandler(BaseCallbackHandler):
    # Captures each tool invocation so the UI can show what the researcher did.
    def __init__(self):
        self.calls: list[dict] = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name", "?")
        self.calls.append({"tool": name, "input": str(input_str)[:120]})


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
        trace = _ToolTraceHandler()
        invoke_config = {"callbacks": [trace]}
        result = sub_agent.invoke(
            {"messages": [HumanMessage(content=user_msg)]},
            config=invoke_config,
        )
        final_text = result["messages"][-1].content
        try:
            sources = parse_sources_payload(final_text)
        except (json.JSONDecodeError, ValueError):
            # Retry once with an explicit error
            retry_msg = (
                "Your previous response was not valid JSON. Return ONLY a JSON array "
                "of source objects, no commentary, no fence."
            )
            result = sub_agent.invoke(
                {"messages": result["messages"] + [HumanMessage(content=retry_msg)]},
                config=invoke_config,
            )
            sources = parse_sources_payload(result["messages"][-1].content)
        return {"sources": sources, "tool_calls": trace.calls}

    return researcher_node
