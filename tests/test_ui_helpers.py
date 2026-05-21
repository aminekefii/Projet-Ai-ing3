"""Unit tests for pure UI helpers (no Streamlit imports)."""
from agent.ui_helpers import initial_dialog_step


def test_empirical_starts_at_upload():
    assert initial_dialog_step("empirical") == "upload"


def test_survey_starts_at_ask():
    assert initial_dialog_step("survey") == "ask"


def test_term_starts_at_ask():
    assert initial_dialog_step("term") == "ask"


def test_unknown_mode_falls_back_to_ask():
    # Defensive: any future mode that isn't 'empirical' should show the Yes/No first.
    assert initial_dialog_step("future-mode") == "ask"
