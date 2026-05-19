import json

from langchain_core.messages import AIMessage


class FakeLLM:
    """Returns a canned JSON response. Mimics ChatOpenAI.invoke()."""
    def __init__(self, response: str):
        self._response = response

    def invoke(self, messages):
        return AIMessage(content=self._response)


def test_intake_returns_outline_from_llm():
    from agent.nodes.intake import intake_node
    fake = FakeLLM(json.dumps({
        "sections": [
            {"title": "Introduction", "bullets": ["context"], "target_words": 400},
            {"title": "Background", "bullets": ["history"], "target_words": 600},
        ]
    }))
    state = {"topic": "X", "mode": "survey"}
    result = intake_node(state, fake)
    assert len(result["outline"]) == 2
    assert result["outline"][0].title == "Introduction"
    assert result["revision_count"] == 0


def test_intake_respects_mode_default_sections():
    """Empirical mode should produce Methods/Results sections by default."""
    from agent.nodes.intake import intake_node
    fake = FakeLLM(json.dumps({
        "sections": [
            {"title": "Methods", "bullets": [], "target_words": 500},
            {"title": "Results", "bullets": [], "target_words": 700},
        ]
    }))
    state = {"topic": "Q3 sales", "mode": "empirical"}
    result = intake_node(state, fake)
    titles = [s.title for s in result["outline"]]
    assert "Methods" in titles
    assert "Results" in titles


def test_intake_raises_on_unknown_mode():
    import pytest
    from agent.nodes.intake import intake_node
    fake = FakeLLM("{}")
    with pytest.raises(ValueError, match="Unknown mode"):
        intake_node({"topic": "X", "mode": "dissertation"}, fake)
