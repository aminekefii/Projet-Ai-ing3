"""Shared pytest fixtures — no API keys required."""
import pytest


@pytest.fixture
def sample_source_pack():
    """Three sources covering Introduction and Background."""
    from agent.state import Source
    return [
        Source(id="src-1", title="Attention Is All You Need", authors=["Vaswani et al."],
               year=2017, url="https://arxiv.org/abs/1706.03762", snippet="Transformer architecture.",
               origin_tool="arxiv", covers_sections=["Introduction", "Background"]),
        Source(id="src-2", title="BERT", authors=["Devlin et al."],
               year=2018, url="https://arxiv.org/abs/1810.04805", snippet="Bidirectional encoders.",
               origin_tool="arxiv", covers_sections=["Background"]),
        Source(id="src-3", title="Transformer (Wikipedia)", authors=[],
               year=None, url="https://en.wikipedia.org/wiki/Transformer",
               snippet="Overview of transformer model.", origin_tool="wikipedia",
               covers_sections=["Introduction"]),
    ]


@pytest.fixture
def sample_outline():
    from agent.state import Section
    return [
        Section(title="Introduction", bullets=["context", "thesis"], target_words=400),
        Section(title="Background", bullets=["history"], target_words=600),
    ]


@pytest.fixture
def sample_state(sample_source_pack, sample_outline):
    from agent.state import TokenUsage
    return {
        "topic": "Transformer attention mechanisms",
        "mode": "survey",
        "outline": sample_outline,
        "user_data": [],
        "sources": sample_source_pack,
        "draft": {},
        "review": None,
        "revision_count": 0,
        "token_usage": TokenUsage(),
        "messages": [],
        "final_output": None,
    }
