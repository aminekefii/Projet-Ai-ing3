import json
from langchain_core.messages import AIMessage


class FakeLLM:
    def __init__(self, response: str):
        self._response = response
    def invoke(self, messages):
        return AIMessage(content=self._response)


def test_reviewer_returns_pass_verdict(sample_state):
    from agent.nodes.reviewer import make_reviewer_node
    sample_state["draft"] = {"Introduction": "good", "Background": "good"}
    sample_state["forced_review_issues"] = []
    fake = FakeLLM(json.dumps({"issues": [], "verdict": "pass"}))
    node = make_reviewer_node(fake)
    result = node(sample_state)
    assert result["review"].verdict == "pass"
    assert result["review"].issues == []


def test_reviewer_includes_forced_issues(sample_state):
    """Drafter-flagged missing_citation issues must end up in the final report."""
    from agent.nodes.reviewer import make_reviewer_node
    from agent.state import ReviewIssue
    sample_state["draft"] = {"Introduction": "weak", "Background": "ok"}
    sample_state["forced_review_issues"] = [
        ReviewIssue(section="Introduction", kind="missing_citation",
                    suggestion="src-99 not in pack")
    ]
    fake = FakeLLM(json.dumps({"issues": [], "verdict": "pass"}))
    node = make_reviewer_node(fake)
    result = node(sample_state)
    assert result["review"].verdict == "revise"  # forced issue upgrades verdict
    assert any(i.kind == "missing_citation" for i in result["review"].issues)


def test_reviewer_combines_llm_and_forced_issues(sample_state):
    from agent.nodes.reviewer import make_reviewer_node
    from agent.state import ReviewIssue
    sample_state["draft"] = {"Introduction": "weak", "Background": "ok"}
    sample_state["forced_review_issues"] = [
        ReviewIssue(section="Introduction", kind="missing_citation", suggestion="x")
    ]
    fake = FakeLLM(json.dumps({
        "issues": [{"section": "Background", "kind": "weak_argument", "suggestion": "y"}],
        "verdict": "revise",
    }))
    node = make_reviewer_node(fake)
    result = node(sample_state)
    assert len(result["review"].issues) == 2
