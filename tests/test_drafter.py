import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage


class FakeLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.last_messages = None

    def invoke(self, messages):
        self.last_messages = messages
        return AIMessage(content=self._responses.pop(0))


class FakeVectorstore:
    """Mimics enough of FAISS for the drafter — only similarity_search is used."""

    def __init__(self, docs: list[Document]):
        self._docs = docs

    def similarity_search(self, query: str, k: int = 4):
        return self._docs[:k]


class RaisingVectorstore:
    def similarity_search(self, query: str, k: int = 4):
        raise RuntimeError("simulated FAISS failure")


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


def test_drafter_without_vectorstore_omits_reference_block(sample_state):
    """With no vectorstore, the user message must NOT contain a REFERENCE PASSAGES block."""
    from agent.nodes.drafter import make_drafter_node
    fake = FakeLLM([
        "Introduction body referencing [src-1].",
        "Background body referencing [src-2].",
    ])
    node = make_drafter_node(fake)
    node(sample_state)
    rendered = fake.last_messages[1].content
    assert "REFERENCE PASSAGES" not in rendered


def test_drafter_with_vectorstore_injects_reference_block(sample_state):
    """With a vectorstore returning 2 docs, the user message contains REFERENCE PASSAGES
    plus both source filenames."""
    from agent.nodes.drafter import make_drafter_node
    vs = FakeVectorstore([
        Document(page_content="chunk A about transformers.",
                 metadata={"source": "lecture.pdf", "page": 1}),
        Document(page_content="chunk B about attention.",
                 metadata={"source": "notes.txt"}),
    ])
    fake = FakeLLM([
        "Intro with [src-1] and (lecture.pdf, page 1).",
        "Background with [src-2] and (notes.txt).",
    ])
    node = make_drafter_node(fake, vectorstore=vs)
    node(sample_state)
    rendered = fake.last_messages[1].content
    assert "REFERENCE PASSAGES" in rendered
    assert "lecture.pdf" in rendered
    assert "notes.txt" in rendered


def test_drafter_with_empty_retrieval_skips_reference_block(sample_state):
    """If similarity_search returns nothing, no REFERENCE PASSAGES block is added."""
    from agent.nodes.drafter import make_drafter_node
    vs = FakeVectorstore([])
    fake = FakeLLM([
        "Intro with [src-1].",
        "Background with [src-2].",
    ])
    node = make_drafter_node(fake, vectorstore=vs)
    node(sample_state)
    rendered = fake.last_messages[1].content
    assert "REFERENCE PASSAGES" not in rendered


def test_drafter_with_failing_vectorstore_degrades_silently(sample_state):
    """If similarity_search raises, the drafter must not crash; the block is just skipped."""
    from agent.nodes.drafter import make_drafter_node
    fake = FakeLLM([
        "Intro with [src-1].",
        "Background with [src-2].",
    ])
    node = make_drafter_node(fake, vectorstore=RaisingVectorstore())
    result = node(sample_state)
    assert "Introduction" in result["draft"]
    rendered = fake.last_messages[1].content
    assert "REFERENCE PASSAGES" not in rendered


def test_drafter_passes_has_documents_to_system_prompt(sample_state):
    """When a vectorstore is provided, the system prompt must include the docs addendum."""
    from agent.nodes.drafter import make_drafter_node
    vs = FakeVectorstore([Document(page_content="x", metadata={"source": "x.pdf"})])
    fake = FakeLLM([
        "Intro [src-1].",
        "Background [src-2].",
    ])
    node = make_drafter_node(fake, vectorstore=vs)
    node(sample_state)
    system_msg = fake.last_messages[0].content
    assert "REFERENCE PASSAGES" in system_msg
