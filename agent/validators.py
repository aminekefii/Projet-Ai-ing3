"""Pure validation helpers — no LLM calls, no I/O. Safe to call from any node."""
from __future__ import annotations

import re

from .state import TokenUsage

CITATION_PATTERN = re.compile(r"\[(src-\d+)\]")

MODEL_ALLOWLIST = frozenset({
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-5-mini",
    "gpt-5",
})


def extract_citations(text: str) -> set[str]:
    """Return the set of citation IDs (like 'src-3') that appear in the text."""
    return set(CITATION_PATTERN.findall(text))


def find_missing_citations(text: str, known_ids: set[str]) -> set[str]:
    """Return citation IDs in the text that are NOT in the known source pack."""
    return extract_citations(text) - known_ids


def update_budget(usage: TokenUsage, input_tokens: int, output_tokens: int) -> TokenUsage:
    """Return a new TokenUsage with accumulated tokens and updated warning/halt flags."""
    new_input = usage.input + input_tokens
    new_output = usage.output + output_tokens
    new_total = new_input + new_output
    return TokenUsage(
        input=new_input,
        output=new_output,
        total=new_total,
        budget=usage.budget,
        warning=new_total >= int(usage.budget * 0.8),
        halt=new_total >= usage.budget,
    )


def validate_model_name(name: str) -> None:
    """Raise ValueError if the model name is not in the allowlist."""
    if name not in MODEL_ALLOWLIST:
        raise ValueError(
            f"Model {name!r} is not in allowlist. "
            f"Allowed: {sorted(MODEL_ALLOWLIST)}"
        )
