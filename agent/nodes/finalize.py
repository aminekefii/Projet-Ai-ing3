"""Finalize node: format the draft as a complete Markdown paper with References."""
from __future__ import annotations

import re

from ..state import PaperState

_CITATION_RE = re.compile(r"\[(src-\d+)\]")


def _format_reference(src) -> str:
    parts = []
    if src.authors:
        parts.append(", ".join(src.authors))
    if src.year:
        parts.append(f"({src.year})")
    parts.append(src.title)
    if src.url:
        parts.append(src.url)
    return ". ".join(parts) + "."


def finalize_node(state: PaperState) -> dict:
    sections_md = "\n\n".join(
        f"## {section.title}\n\n{state['draft'].get(section.title, '')}"
        for section in state["outline"]
    )
    cited_ids_in_order: list[str] = []
    for section in state["outline"]:
        body = state["draft"].get(section.title, "")
        for cid in _CITATION_RE.findall(body):
            if cid not in cited_ids_in_order:
                cited_ids_in_order.append(cid)
    sources_by_id = {s.id: s for s in state["sources"]}
    refs_md = "\n".join(
        f"- **[{sid}]** {_format_reference(sources_by_id[sid])}"
        for sid in cited_ids_in_order if sid in sources_by_id
    )
    paper = (
        f"# {state['topic']}\n\n"
        f"{sections_md}\n\n"
        f"## References\n\n{refs_md}\n"
    )
    return {"final_output": paper}
