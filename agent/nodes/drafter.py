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
