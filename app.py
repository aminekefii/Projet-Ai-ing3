import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import DEFAULT_MODEL, build_agent

load_dotenv()

st.set_page_config(
    page_title="University Writing Assistant",
    page_icon="🎓",
    layout="wide",
)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "checkpointer" not in st.session_state:
    st.session_state.checkpointer = MemorySaver()
if "history" not in st.session_state:
    st.session_state.history = []
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.0
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
if "indexed_files" not in st.session_state:
    st.session_state.indexed_files = []


with st.sidebar:
    st.title("⚙️ Settings")

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.success("OpenAI API key loaded")
    else:
        st.error("OPENAI_API_KEY missing — set it in .env")

    st.session_state.temperature = st.slider(
        "Temperature", 0.0, 1.0, st.session_state.temperature, 0.1
    )

    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.checkpointer = MemorySaver()
        st.session_state.history = []
        st.rerun()

    st.divider()
    st.markdown("### 📄 Readings & notes (RAG)")
    uploaded = st.file_uploader(
        "Upload course readings, notes, or sources (PDF / TXT)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded and st.button("📚 Index readings", use_container_width=True):
        from agent.rag import index_uploaded_files
        with st.spinner("Chunking and embedding…"):
            vs, summary = index_uploaded_files(uploaded)
        if vs is None:
            st.warning("No usable text extracted from the uploaded files.")
        else:
            st.session_state.vectorstore = vs
            st.session_state.indexed_files = summary
            total_chunks = sum(n for _, n in summary)
            st.success(f"Indexed {len(summary)} file(s), {total_chunks} chunks.")

    if st.session_state.indexed_files:
        st.markdown("**Indexed:**")
        for name, n in st.session_state.indexed_files:
            st.caption(f"• `{name}` — {n} chunks")
        if st.button("🧹 Clear readings", use_container_width=True):
            st.session_state.vectorstore = None
            st.session_state.indexed_files = []
            st.rerun()

    st.divider()
    st.markdown("### 🛠️ Available tools")
    base_tools = (
        "- **Web search** — current sources, statistics, news (DuckDuckGo)\n"
        "- **Wikipedia** — background, definitions, biographies\n"
        "- **arXiv** — peer-reviewed and pre-print research\n"
        "- **Python REPL** — math, statistics, unit conversion"
    )
    if st.session_state.vectorstore is not None:
        base_tools += "\n- **Document search** — your uploaded readings"
    st.markdown(base_tools)

    st.divider()
    st.caption(f"Thread: `{st.session_state.thread_id[:8]}…`")


def get_agent():
    return build_agent(
        model_name=DEFAULT_MODEL,
        temperature=st.session_state.temperature,
        checkpointer=st.session_state.checkpointer,
        vectorstore=st.session_state.vectorstore,
    )


def truncate(text: str, n: int = 1500) -> str:
    text = str(text)
    return text if len(text) <= n else text[:n] + "\n\n…(truncated)"


st.title("🎓 University Writing Assistant")
st.caption("Source-grounded help for university articles — outline, draft, cite, revise. Web · Wikipedia · arXiv · Python · Your readings.")

for entry in st.session_state.history:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])

user_input = st.chat_input("Ask for help with your paper — outline, draft a section, find sources, revise…")

if user_input:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Cannot run — set OPENAI_API_KEY in your .env file first.")
        st.stop()

    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        final_text = ""
        tools_used: list[str] = []
        agent = get_agent()

        try:
            for chunk in agent.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
                stream_mode="updates",
            ):
                for _node, payload in chunk.items():
                    if not isinstance(payload, dict):
                        continue
                    for msg in payload.get("messages", []):
                        if isinstance(msg, AIMessage):
                            for tc in (msg.tool_calls or []):
                                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "?")
                                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                                tools_used.append(name)
                                with st.status(
                                    f"🛠️ Calling `{name}`",
                                    expanded=False,
                                ) as status:
                                    st.json(args)
                                    status.update(state="complete")
                            if msg.content:
                                final_text = msg.content
                                st.markdown(msg.content)
                        elif isinstance(msg, ToolMessage):
                            with st.status(
                                f"📥 `{msg.name}` returned",
                                expanded=False,
                            ) as status:
                                st.markdown(truncate(msg.content))
                                status.update(state="complete")

            if tools_used:
                summary = ", ".join(f"`{t}`" for t in tools_used)
                st.success(f"✅ Grounded in {len(tools_used)} tool call(s): {summary}")
            else:
                st.warning("⚠️ Answered without invoking any tool — response is from the model's own knowledge.")
        except Exception as e:
            err = f"⚠️ Agent error: `{type(e).__name__}` — {e}"
            st.error(err)
            final_text = err

        # Persist the answer + a one-line tool footer so it stays visible after rerun
        footer = ""
        if tools_used:
            footer = f"\n\n---\n_✅ Grounded in {len(tools_used)} tool call(s): {', '.join(f'`{t}`' for t in tools_used)}_"
        elif final_text and not final_text.startswith("⚠️"):
            footer = "\n\n---\n_⚠️ Answered without tools — from the model's own knowledge._"

        st.session_state.history.append(
            {"role": "assistant", "content": (final_text or "_(no answer produced)_") + footer}
        )
