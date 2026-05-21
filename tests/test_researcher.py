import pytest


def test_parse_sources_payload_happy_path():
    from agent.nodes.researcher import parse_sources_payload
    payload = """[
        {"id": "src-1", "title": "Attention", "authors": ["Vaswani"],
         "year": 2017, "url": "https://arxiv.org/...", "snippet": "...",
         "origin_tool": "arxiv", "covers_sections": ["Introduction"]}
    ]"""
    sources = parse_sources_payload(payload)
    assert len(sources) == 1
    assert sources[0].id == "src-1"


def test_parse_sources_payload_dedupes_by_url():
    from agent.nodes.researcher import parse_sources_payload
    payload = """[
        {"id": "src-1", "title": "A", "url": "https://x", "origin_tool": "arxiv"},
        {"id": "src-2", "title": "A duplicate", "url": "https://x", "origin_tool": "arxiv"}
    ]"""
    sources = parse_sources_payload(payload)
    assert len(sources) == 1


def test_parse_sources_payload_caps_at_15():
    from agent.nodes.researcher import parse_sources_payload
    items = [{"id": f"src-{i}", "title": f"t{i}", "url": f"u{i}", "origin_tool": "arxiv"}
             for i in range(20)]
    import json
    sources = parse_sources_payload(json.dumps(items))
    assert len(sources) == 15


def test_parse_sources_payload_strips_markdown_fence():
    """LLMs sometimes wrap JSON in ```json fences. Parser must tolerate that."""
    from agent.nodes.researcher import parse_sources_payload
    payload = '```json\n[{"id": "src-1", "title": "t", "url": "u", "origin_tool": "arxiv"}]\n```'
    sources = parse_sources_payload(payload)
    assert len(sources) == 1


def test_researcher_prompt_includes_docs_addendum_when_has_documents():
    from agent.prompts import get_researcher_prompt
    p = get_researcher_prompt("survey", has_documents=True)
    assert "DOCUMENTS UPLOADED" in p


def test_researcher_prompt_omits_docs_addendum_by_default():
    from agent.prompts import get_researcher_prompt
    p = get_researcher_prompt("survey")
    assert "DOCUMENTS UPLOADED" not in p


def test_researcher_prompt_omits_docs_addendum_when_has_documents_false():
    from agent.prompts import get_researcher_prompt
    p = get_researcher_prompt("survey", has_documents=False)
    assert "DOCUMENTS UPLOADED" not in p
