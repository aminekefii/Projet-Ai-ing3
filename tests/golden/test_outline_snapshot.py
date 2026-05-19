"""Golden test: outline shape for a fixed (topic, mode) at temp=0.

On first run with an OPENAI_API_KEY set, writes the snapshot.
On subsequent runs, asserts the outline shape matches.
Skips cleanly when OPENAI_API_KEY is missing."""
import json
import os
from pathlib import Path

import pytest

SNAPSHOT_PATH = Path(__file__).parent / "survey_attention_outline.json"


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
def test_survey_outline_shape_stable():
    from langchain_openai import ChatOpenAI
    from agent.nodes.intake import intake_node

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    result = intake_node(
        {"topic": "Transformer attention mechanisms", "mode": "survey"},
        llm,
    )
    shape = {
        "section_count": len(result["outline"]),
        "titles": [s.title for s in result["outline"]],
        "target_words": [s.target_words for s in result["outline"]],
    }
    if not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.write_text(json.dumps(shape, indent=2))
        pytest.skip(f"Wrote initial snapshot to {SNAPSHOT_PATH}; rerun to assert")
    expected = json.loads(SNAPSHOT_PATH.read_text())
    assert shape == expected, (
        f"Outline shape drifted.\nExpected: {expected}\nGot: {shape}\n"
        f"If this drift is intentional, delete {SNAPSHOT_PATH} and rerun."
    )
