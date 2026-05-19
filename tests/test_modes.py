import pytest


def test_all_three_profiles_load():
    from agent.modes import PROFILES
    assert set(PROFILES.keys()) == {"survey", "empirical", "term"}


def test_get_profile_returns_correct_mode():
    from agent.modes import get_profile
    assert get_profile("survey").name == "survey"
    assert get_profile("empirical").name == "empirical"
    assert get_profile("term").name == "term"


def test_get_profile_raises_for_unknown_mode():
    from agent.modes import get_profile
    with pytest.raises(ValueError, match="Unknown mode"):
        get_profile("dissertation")


def test_each_profile_has_non_empty_sections():
    from agent.modes import PROFILES
    for name, profile in PROFILES.items():
        assert len(profile.default_sections) >= 3, f"{name} has fewer than 3 sections"
        for section in profile.default_sections:
            assert section.title
            assert section.target_words > 0


def test_term_mode_skips_reviewer_revision():
    from agent.modes import get_profile
    assert get_profile("term").skip_reviewer_revision is True
    assert get_profile("survey").skip_reviewer_revision is False
    assert get_profile("empirical").skip_reviewer_revision is False
