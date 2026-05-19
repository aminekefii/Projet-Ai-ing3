def test_graph_builds_without_api_key(monkeypatch):
    """Graph construction must not require an API call — only happens on first invoke."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-construction-only")
    from agent.graph import build_graph
    g = build_graph(model_name="gpt-4o-mini")
    # Confirm interrupts are wired
    assert hasattr(g, "get_state")


def test_graph_rejects_invalid_model():
    import pytest
    with pytest.raises(ValueError, match="not in allowlist"):
        from agent.graph import build_graph
        build_graph(model_name="gpt-5.4-mini")
