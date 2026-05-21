"""Pure helpers for the New Paper page UI.

Kept separate from the page module so they can be unit-tested without
importing Streamlit (which pulls in a lot and is awkward to fake).
"""


def initial_dialog_step(mode: str) -> str:
    """Return the initial step name for the reference-file dialog.

    Empirical papers go straight to the upload step (a data file is required).
    All other modes (survey, term, anything new) start at the Yes/No question.
    """
    return "upload" if mode == "empirical" else "ask"
