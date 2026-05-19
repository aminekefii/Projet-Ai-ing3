import pytest


def test_extract_citations_finds_all():
    from agent.validators import extract_citations
    text = "Claim one [src-1]. Claim two [src-42]. No cite here."
    assert extract_citations(text) == {"src-1", "src-42"}


def test_extract_citations_handles_empty():
    from agent.validators import extract_citations
    assert extract_citations("") == set()


def test_find_missing_citations_returns_unknown_only():
    from agent.validators import find_missing_citations
    text = "Real [src-1], fake [src-99], real [src-2]."
    assert find_missing_citations(text, {"src-1", "src-2"}) == {"src-99"}


def test_budget_warning_at_80_percent():
    from agent.state import TokenUsage
    from agent.validators import update_budget
    usage = TokenUsage(budget=10_000)
    new = update_budget(usage, input_tokens=8_000, output_tokens=0)
    assert new.warning is True
    assert new.halt is False


def test_budget_halt_at_100_percent():
    from agent.state import TokenUsage
    from agent.validators import update_budget
    usage = TokenUsage(budget=10_000)
    new = update_budget(usage, input_tokens=10_000, output_tokens=0)
    assert new.halt is True


def test_budget_accumulates():
    from agent.state import TokenUsage
    from agent.validators import update_budget
    usage = TokenUsage(budget=10_000)
    after1 = update_budget(usage, 1_000, 500)
    after2 = update_budget(after1, 2_000, 500)
    assert after2.total == 4_000


def test_model_name_allowlist_accepts_known():
    from agent.validators import validate_model_name
    validate_model_name("gpt-4o-mini")  # should not raise


def test_model_name_allowlist_rejects_fake():
    from agent.validators import validate_model_name
    with pytest.raises(ValueError, match="not in allowlist"):
        validate_model_name("gpt-5.4-mini")
