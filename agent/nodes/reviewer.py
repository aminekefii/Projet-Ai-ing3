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
