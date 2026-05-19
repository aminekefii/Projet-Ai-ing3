import pytest
from langchain_core.messages import AIMessage


class FakeLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def invoke(self, messages):
        return AIMessage(content=self._responses.pop(0))


def test_drafter_writes_all_sections(sample_state):
    from agent.nodes.drafter import make_drafter_node
    fake = FakeLLM([
        "Introduction body referencing [src-1].",
        "Background body referencing [src-2] and [src-1].",
    ])
    node = make_drafter_node(fake)
    result = node(sample_state)
    assert set(result["draft"].keys()) == {"Introduction", "Background"}
    assert "[src-1]" in result["draft"]["Introduction"]


def test_drafter_flags_hallucinated_citations(sample_state):
    """A draft referencing [src-99] (not in pack) must produce a missing_citation issue."""
    from agent.nodes.drafter import make_drafter_node
    fake = FakeLLM([
        "Intro with bogus citation [src-99].",
        "Background with real [src-2].",
    ])
    node = make_drafter_node(fake)
    result = node(sample_state)
    forced = result.get("forced_review_issues", [])
    kinds = [i.kind for i in forced]
    assert "missing_citation" in kinds
    sections_flagged = [i.section for i in forced if i.kind == "missing_citation"]
    assert "Introduction" in sections_flagged


def test_drafter_revision_pass_uses_review_issues(sample_state):
    """When revision_count == 0 but review.issues exist, drafter must address them."""
    from agent.nodes.drafter import make_drafter_node
    from agent.state import ReviewReport, ReviewIssue
    sample_state["review"] = ReviewReport(
        verdict="revise",
        issues=[ReviewIssue(section="Introduction", kind="weak_argument",
                            suggestion="strengthen thesis")],
    )
    sample_state["draft"] = {"Introduction": "original", "Background": "original"}
    fake = FakeLLM(["Revised intro with [src-1].", "Revised background with [src-2]."])
    node = make_drafter_node(fake)
    result = node(sample_state)
    assert result["revision_count"] == 1
    assert result["draft"]["Introduction"] != "original"
