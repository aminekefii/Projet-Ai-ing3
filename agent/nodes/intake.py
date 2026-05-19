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
