def test_finalize_markdown_includes_all_sections(sample_state):
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {
        "Introduction": "intro body [src-1]",
        "Background": "background body [src-2]",
    }
    result = finalize_node(sample_state)
    output = result["final_output"]
    assert "# Transformer attention mechanisms" in output
    assert "## Introduction" in output
    assert "## Background" in output
    assert "intro body" in output


def test_finalize_includes_references_section(sample_state):
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "[src-1] claim.", "Background": "[src-2] more."}
    result = finalize_node(sample_state)
    output = result["final_output"]
    assert "## References" in output
    assert "Attention Is All You Need" in output  # from src-1 in fixture


def test_finalize_orders_references_by_id_appearance(sample_state):
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "[src-3] then [src-1]"}
    result = finalize_node(sample_state)
    refs_section = result["final_output"].split("## References")[1]
    # src-3 cited first should appear before src-1 in references
    assert refs_section.index("Transformer (Wikipedia)") < refs_section.index("Attention Is All You Need")


def test_finalize_uses_paper_title_when_set(sample_state):
    """When paper_title is in state, it should replace topic as the H1."""
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "body", "Background": "more body"}
    sample_state["paper_title"] = "A Custom Paper Title"
    result = finalize_node(sample_state)
    first_line = result["final_output"].split("\n", 1)[0]
    assert first_line == "# A Custom Paper Title"


def test_finalize_falls_back_to_topic_when_paper_title_empty(sample_state):
    """Empty-string paper_title should fall back to topic, not produce '# '."""
    from agent.nodes.finalize import finalize_node
    sample_state["draft"] = {"Introduction": "body"}
    sample_state["paper_title"] = ""  # explicit empty
    result = finalize_node(sample_state)
    first_line = result["final_output"].split("\n", 1)[0]
    assert first_line == "# Transformer attention mechanisms"  # topic from fixture
