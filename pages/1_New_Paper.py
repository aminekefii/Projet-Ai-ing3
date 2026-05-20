"""New Paper page — runs the multi-agent graph with checkpoint cards."""
import io
import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from agent.checkpointer import get_checkpointer
from agent import db

from agent.graph import DEFAULT_MODEL, build_graph
from agent.state import Section, Source, TokenUsage

load_dotenv()

st.set_page_config(page_title="New Paper · Research Paper Agent", page_icon="📑", layout="wide")

# --- Session state init (shared with dashboard) ---
defaults = {
    "thread_id": str(uuid.uuid4()),
    "checkpointer": None,
    "vectorstore": None,
    "indexed_files": [],
    "mode": "survey",
    "pending_checkpoint": None,
    "run_started": False,
    "trace": [],
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

MODE_LABELS = {
    "survey": "📚 Literature Review",
    "empirical": "📊 Empirical Paper",
    "term": "📝 Term Paper",
}


# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Settings")

    if st.button("🗑️ Start over", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v if not callable(v) else v
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.checkpointer = get_checkpointer()
        st.session_state.pop("_persisted_complete", None)
        st.rerun()

    if st.button("← Back to dashboard", use_container_width=True):
        st.switch_page("app.py")

    st.divider()
    st.markdown("### 📄 Readings / data")
    uploaded = st.file_uploader(
        "Upload PDF or TXT (CSV for empirical mode)",
        type=["pdf", "txt", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded and st.button("📚 Index", use_container_width=True):
        from agent.rag import index_uploaded_files
        with st.spinner("Indexing…"):
            vs, summary = index_uploaded_files(uploaded)
        if vs is None:
            st.warning("No usable text extracted.")
        else:
            st.session_state.vectorstore = vs
            st.session_state.indexed_files = summary
            # Persist blobs to Supabase Storage so they survive a restart.
            upload_failures = []
            for f in uploaded:
                try:
                    db.upload_file(st.session_state.thread_id, f)
                except Exception as e:
                    upload_failures.append((f.name, str(e)))
            if upload_failures:
                for name, err in upload_failures:
                    st.warning(f"Could not save '{name}' to Storage: {err}")
            st.success(f"Indexed {len(summary)} file(s).")

    if st.session_state.indexed_files:
        for name, n in st.session_state.indexed_files:
            st.caption(f"• `{name}` — {n} chunks")

    st.divider()
    st.caption(f"Thread: `{st.session_state.thread_id[:8]}…`")


# --- Main panel ---
st.title(MODE_LABELS[st.session_state.mode])
st.caption("Multi-agent: researcher → drafter → reviewer. You approve at each checkpoint.")


def get_graph():
    return build_graph(
        model_name=DEFAULT_MODEL,
        vectorstore=st.session_state.vectorstore,
        checkpointer=st.session_state.checkpointer,
    )


def config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def render_trace():
    for entry in st.session_state.trace:
        if entry["kind"] == "user":
            with st.chat_message("user"):
                st.markdown(entry["content"])
        elif entry["kind"] == "node":
            with st.chat_message("assistant"):
                st.markdown(f"**✓ {entry['node']}** complete")
                if entry.get("detail"):
                    with st.expander("details"):
                        st.json(entry["detail"])
        elif entry["kind"] == "final":
            with st.chat_message("assistant"):
                st.markdown(entry["content"])


def stream_until_interrupt(initial_input=None):
    graph = get_graph()
    for event in graph.stream(initial_input, config=config(), stream_mode="updates"):
        for node, payload in event.items():
            st.session_state.trace.append({
                "kind": "node", "node": node,
                "detail": {k: str(v)[:200] for k, v in (payload or {}).items()},
            })
    snapshot = graph.get_state(config())
    if snapshot.next:
        st.session_state.pending_checkpoint = snapshot.next[0]
    else:
        st.session_state.pending_checkpoint = None


def render_checkpoint_card():
    graph = get_graph()
    snapshot = graph.get_state(config())
    cp = st.session_state.pending_checkpoint

    if cp == "researcher":
        st.subheader("Checkpoint 1: Confirm outline")
        outline = snapshot.values.get("outline", [])
        edited_titles = []
        edited_bullets = []
        edited_words = []
        for i, sec in enumerate(outline):
            with st.expander(f"§ {sec.title}", expanded=True):
                edited_titles.append(st.text_input("Title", sec.title, key=f"t{i}"))
                edited_bullets.append(st.text_area("Bullets (one per line)",
                                                    "\n".join(sec.bullets), key=f"b{i}"))
                edited_words.append(st.number_input("Target words", value=sec.target_words,
                                                     step=50, key=f"w{i}"))
        col1, col2 = st.columns(2)
        if col1.button("✅ Approve outline → start research", type="primary",
                       use_container_width=True):
            new_outline = [
                Section(title=t, bullets=[b for b in bs.split("\n") if b.strip()],
                        target_words=int(w))
                for t, bs, w in zip(edited_titles, edited_bullets, edited_words)
            ]
            graph.update_state(config(), {"outline": new_outline})
            st.session_state.pending_checkpoint = None
            with st.spinner("Researching…"):
                stream_until_interrupt(None)
            st.rerun()
        if col2.button("❌ Cancel paper", use_container_width=True):
            st.session_state.pending_checkpoint = None
            st.session_state.run_started = False
            st.rerun()

    elif cp == "drafter":
        st.subheader("Checkpoint 2: Approve source pack")
        sources = snapshot.values.get("sources", [])
        keep = []
        for src in sources:
            label = f"**{src.id}** — {src.title} ({src.origin_tool})"
            if st.checkbox(label, value=True, key=f"src{src.id}"):
                keep.append(src)
            if src.url:
                st.caption(src.url)
        if st.button(f"✅ Draft with {len(keep)} sources", type="primary",
                     use_container_width=True):
            graph.update_state(config(), {"sources": keep})
            st.session_state.pending_checkpoint = None
            with st.spinner("Drafting…"):
                stream_until_interrupt(None)
            st.rerun()

    elif cp == "finalize":
        st.subheader("Checkpoint 3: Review draft")
        draft = snapshot.values.get("draft", {})
        review = snapshot.values.get("review")
        if review and review.issues:
            with st.expander(f"⚠️ Reviewer flagged {len(review.issues)} issue(s)"):
                for i in review.issues:
                    st.markdown(f"- **[{i.kind}]** {i.section}: {i.suggestion}")
        for title, body in draft.items():
            with st.expander(f"## {title}", expanded=False):
                st.markdown(body)
        if st.button("✅ Approve → finalize", type="primary", use_container_width=True):
            st.session_state.pending_checkpoint = None
            with st.spinner("Finalizing…"):
                stream_until_interrupt(None)
            st.rerun()


# --- Resume an existing paper if requested ---
resume_id = st.session_state.pop("resume_paper_id", None)
if resume_id:
    paper = db.get_paper(resume_id)
    if paper is None:
        st.error(f"Paper {resume_id[:8]}… not found.")
        st.stop()
    st.session_state.thread_id = resume_id
    st.session_state.mode = paper["mode"]
    st.session_state.trace = [{"kind": "user", "content": paper["topic"]}]
    st.session_state.run_started = True
    st.session_state.pending_checkpoint = None
    st.session_state._persisted_complete = (paper["status"] == "complete")

    # Re-download persisted files and rebuild FAISS in-memory.
    file_rows = db.list_paper_files(resume_id)
    if file_rows:
        from agent.rag import index_uploaded_files

        class _ResumedFile:
            def __init__(self, name, payload):
                self.name = name
                self._buf = io.BytesIO(payload)
                self.size = len(payload)
            def getvalue(self):
                return self._buf.getvalue()
            def read(self, *args, **kwargs):
                return self._buf.read(*args, **kwargs)
            def seek(self, *args, **kwargs):
                return self._buf.seek(*args, **kwargs)

        resumed_files = []
        for row in file_rows:
            try:
                blob = db.download_file(row["storage_path"])
                resumed_files.append(_ResumedFile(row["file_name"], blob))
            except Exception as e:
                st.warning(f"File '{row['file_name']}' missing from Storage — continuing without it ({e})")
        if resumed_files:
            with st.spinner("Re-indexing saved files…"):
                vs, summary = index_uploaded_files(resumed_files)
            if vs is not None:
                st.session_state.vectorstore = vs
                st.session_state.indexed_files = summary

    # Sync the pending checkpoint from PostgresSaver-backed graph state.
    graph = build_graph(
        model_name=DEFAULT_MODEL,
        vectorstore=st.session_state.vectorstore,
        checkpointer=st.session_state.checkpointer,
    )
    snapshot = graph.get_state({"configurable": {"thread_id": resume_id}})
    if snapshot.next:
        st.session_state.pending_checkpoint = snapshot.next[0]


# --- Main flow ---
render_trace()

if st.session_state.pending_checkpoint:
    render_checkpoint_card()
elif st.session_state.run_started:
    # Run completed
    graph = get_graph()
    snapshot = graph.get_state(config())
    final = snapshot.values.get("final_output")
    if final:
        if not st.session_state.get("_persisted_complete"):
            try:
                db.mark_complete(st.session_state.thread_id, final)
                st.session_state._persisted_complete = True
            except Exception as e:
                st.warning(f"Could not save paper to history: {e}")
        st.success("📑 Paper complete")
        col_md, col_pdf = st.columns(2)
        col_md.download_button(
            "⬇️ Download Markdown", final,
            file_name="paper.md", mime="text/markdown",
            use_container_width=True,
        )
        try:
            from agent.export_pdf import markdown_to_pdf_bytes
            pdf_bytes = markdown_to_pdf_bytes(final)
            col_pdf.download_button(
                "📄 Download PDF", pdf_bytes,
                file_name="paper.pdf", mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            col_pdf.warning(f"PDF export unavailable: {e}")
        with st.expander("Preview", expanded=True):
            st.markdown(final)
else:
    topic = st.chat_input("Paper topic (e.g. 'Transformer attention mechanisms')")
    if topic:
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Set OPENAI_API_KEY in .env first.")
            st.stop()
        st.session_state.trace.append({"kind": "user", "content": topic})
        st.session_state.run_started = True
        try:
            db.update_paper_topic(st.session_state.thread_id, topic)
        except Exception as e:
            st.warning(f"Could not save topic to history: {e}")
        with st.spinner("Generating outline…"):
            user_data = []
            if st.session_state.vectorstore is not None and st.session_state.mode == "empirical":
                user_data = [
                    d for d in st.session_state.vectorstore.docstore._dict.values()
                ][:10]
            stream_until_interrupt({
                "topic": topic,
                "mode": st.session_state.mode,
                "user_data": user_data,
                "token_usage": TokenUsage(),
                "messages": [],
            })
        st.rerun()
