import pytest
from pydantic import ValidationError


def test_section_defaults():
    from agent.state import Section
    s = Section(title="Intro")
    assert s.bullets == []
    assert s.target_words == 500


def test_source_requires_id_title_origin_tool():
    from agent.state import Source
    s = Source(id="src-1", title="t", origin_tool="arxiv")
    assert s.authors == []
    assert s.year is None


def test_source_origin_tool_must_be_allowed():
    from agent.state import Source
    with pytest.raises(ValidationError):
        Source(id="src-1", title="t", origin_tool="random_tool")


def test_review_report_verdict_must_be_pass_or_revise():
    from agent.state import ReviewReport
    with pytest.raises(ValidationError):
        ReviewReport(verdict="maybe")


def test_review_issue_kind_constraints():
    from agent.state import ReviewIssue
    with pytest.raises(ValidationError):
        ReviewIssue(section="Intro", kind="nonsense", suggestion="x")


def test_token_usage_defaults():
    from agent.state import TokenUsage
    u = TokenUsage()
    assert u.total == 0
    assert u.budget == 200_000
    assert u.warning is False
    assert u.halt is False
