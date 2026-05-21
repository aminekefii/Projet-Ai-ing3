"""Dashboard / landing page — pick a paper type to start."""
import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from agent.checkpointer import get_checkpointer
from agent import db

load_dotenv()

st.set_page_config(page_title="Research Paper Agent", page_icon="📑", layout="wide")

# --- Session state init (shared with New Paper page) ---
defaults = {
    "thread_id": str(uuid.uuid4()),
    "checkpointer": None,
    "vectorstore": None,
    "indexed_files": [],
    "mode": "survey",
    "pending_checkpoint": None,
    "run_started": False,
    "trace": [],
    "file_choice": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.checkpointer is None:
    try:
        st.session_state.checkpointer = get_checkpointer()
    except RuntimeError as e:
        st.error(f"Supabase env error: {e} — see .env.example")
        st.stop()

# Hide Streamlit's auto-generated multipage nav (we use custom buttons).
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Settings")

    if os.getenv("OPENAI_API_KEY"):
        st.success("OpenAI API key loaded")
    else:
        st.error("OPENAI_API_KEY missing — set it in .env")

    st.divider()
    st.caption(f"Thread: `{st.session_state.thread_id[:8]}…`")


# --- Main panel ---
st.title("📑 Research Paper Agent")
st.caption("Multi-agent academic writing assistant — researcher → drafter → reviewer, with human checkpoints.")

# CSS: pin each mode card's Start button to the bottom so all three buttons
# line up at the same vertical position across the row. Needs flex+height
# applied at every level of the wrapper chain — the previous shorter
# version only flex'd the inner block, but Streamlit's intermediate
# wrapper div has no height set, so the flex didn't propagate down.
st.html(
    """
    <style>
    [data-testid="stVerticalBlockBorderWrapper"] {
        display: flex;
        flex-direction: column;
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div:first-child,
    [data-testid="stVerticalBlockBorderWrapper"] > div:first-child > [data-testid="stVerticalBlock"] {
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;
        height: 100%;
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div:first-child > [data-testid="stVerticalBlock"] > [data-testid="element-container"]:last-child {
        margin-top: auto;
    }
    </style>
    """
)

st.markdown("## Start creating your paper")
st.write("Pick the type that matches what you're writing.")
st.write("")

MODES = [
    {
        "key": "survey",
        "icon": "📚",
        "title": "Literature Review",
        "tagline": "Synthesize peer-reviewed work on a topic.",
        "features": [
            "5 sections: Intro · Background · Related Work · Discussion · Conclusion",
            "Researcher gathers 8–15 sources from arXiv, Wikipedia, web",
            "Reviewer revision loop included",
        ],
    },
    {
        "key": "empirical",
        "icon": "📊",
        "title": "Empirical Paper",
        "tagline": "Built around your own uploaded data.",
        "features": [
            "5 sections: Intro · Methods · Results · Discussion · Conclusion",
            "Data analyzer runs Python on your CSV / PDF",
            "Reviewer revision loop included",
        ],
    },
    {
        "key": "term",
        "icon": "📝",
        "title": "Term Paper",
        "tagline": "Standard university essay.",
        "features": [
            "3 sections: Intro · Body · Conclusion",
            "Single drafter pass — no review loop",
            "Faster and cheaper than the other two modes",
        ],
    },
]

cols = st.columns(3, gap="medium")
for col, mode in zip(cols, MODES):
    with col:
        with st.container(border=True, height=400):
            st.markdown(f"### {mode['icon']} {mode['title']}")
            st.caption(mode["tagline"])
            st.markdown("\n".join(f"- {f}" for f in mode["features"]))
            st.write("")
            if st.button(
                f"Start →",
                key=f"start_{mode['key']}",
                use_container_width=True,
                type="primary",
            ):
                new_id = str(uuid.uuid4())
                try:
                    db.create_paper(new_id, topic="(untitled)", mode=mode["key"])
                except Exception as e:
                    st.error(f"Could not reach Supabase: {e}")
                    st.stop()
                st.session_state.mode = mode["key"]
                st.session_state.thread_id = new_id
                st.session_state.checkpointer = get_checkpointer()
                st.session_state.pending_checkpoint = None
                st.session_state.run_started = False
                st.session_state.trace = []
                st.session_state.file_choice = None
                st.switch_page("pages/1_New_Paper.py")

st.divider()

# --- My papers ---
st.markdown("## 📂 My papers")
try:
    rows = db.list_papers()
except Exception as e:
    st.error(f"Could not reach Supabase: {e}")
    rows = []

if not rows:
    st.caption("No saved papers yet. Pick a mode above to start one.")
else:
    for row in rows:
        status_icon = "✅" if row["status"] == "complete" else "✏️"
        label = f"{status_icon}  **{row['topic']}**  ·  _{row['mode']}_  ·  {row['updated_at'][:10]}"
        col_label, col_del = st.columns([9, 1])
        if col_label.button(label, key=f"resume_{row['id']}", use_container_width=True):
            st.session_state.resume_paper_id = row["id"]
            st.switch_page("pages/1_New_Paper.py")
        if col_del.button("🗑️", key=f"del_{row['id']}", help="Delete this paper", use_container_width=True):
            try:
                db.delete_paper(row["id"])
            except Exception as e:
                st.error(f"Could not delete: {e}")
            else:
                st.rerun()

st.divider()
st.caption(
    "📖 At each checkpoint (outline → sources → draft) you approve or edit before the graph continues. "
    "Threads and uploaded files persist in Supabase."
)
