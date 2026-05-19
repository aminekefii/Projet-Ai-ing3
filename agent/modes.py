"""Mode profiles — same graph, swapped prompts and templates."""
from __future__ import annotations

from dataclasses import dataclass

from .state import Section


@dataclass
class ModeProfile:
    name: str
    default_sections: list[Section]
    researcher_addendum: str
    drafter_addendum: str
    skip_reviewer_revision: bool = False


SURVEY = ModeProfile(
    name="survey",
    default_sections=[
        Section(title="Introduction", target_words=400),
        Section(title="Background", target_words=600),
        Section(title="Related Work", target_words=800),
        Section(title="Discussion", target_words=600),
        Section(title="Conclusion", target_words=300),
    ],
    researcher_addendum=(
        "Focus on landmark and recent peer-reviewed work. "
        "Prefer arXiv and journal sources over Wikipedia for substantive claims."
    ),
    drafter_addendum=(
        "Adopt the register of a literature review: synthesize multiple sources per "
        "paragraph, contrast positions, do not introduce claims beyond the source pack."
    ),
)

EMPIRICAL = ModeProfile(
    name="empirical",
    default_sections=[
        Section(title="Introduction", target_words=400),
        Section(title="Methods", target_words=500),
        Section(title="Results", target_words=700),
        Section(title="Discussion", target_words=600),
        Section(title="Conclusion", target_words=300),
    ],
    researcher_addendum=(
        "Find prior work relevant to the user's empirical data. "
        "The user supplies the data itself; the source pack contextualizes it."
    ),
    drafter_addendum=(
        "In Methods and Results, ground every quantitative claim in the analyzer's "
        "computed stats (passed via state). Cite external sources only for prior work."
    ),
)

TERM = ModeProfile(
    name="term",
    default_sections=[
        Section(title="Introduction", target_words=300),
        Section(title="Body", target_words=1200),
        Section(title="Conclusion", target_words=300),
    ],
    researcher_addendum="Find 4-8 sources covering the main argument. Quality over quantity.",
    drafter_addendum="Argumentative essay register. Clear thesis, topic sentences, hedged but assertive.",
    skip_reviewer_revision=True,
)

PROFILES: dict[str, ModeProfile] = {
    "survey": SURVEY,
    "empirical": EMPIRICAL,
    "term": TERM,
}


def get_profile(mode: str) -> ModeProfile:
    if mode not in PROFILES:
        raise ValueError(f"Unknown mode {mode!r}. Allowed: {sorted(PROFILES)}")
    return PROFILES[mode]
