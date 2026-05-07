from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from .prompts import get_prompt
from .tools import build_tools

DEFAULT_MODEL = "gpt-5.4-mini"


def build_agent(
    model_name: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    checkpointer: MemorySaver | None = None,
    vectorstore=None,
):
    """Construct a ReAct research agent backed by OpenAI.

    The agent plans, calls tools, and reasons over their outputs in a loop
    until it produces a final answer. The optional checkpointer persists
    conversation state across turns (keyed by thread_id at invocation time).
    Passing a vectorstore enables a document_search tool over the user's uploads.
    """
    llm = ChatOpenAI(model=model_name, temperature=temperature)
    tools = build_tools(vectorstore=vectorstore)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=get_prompt(has_documents=vectorstore is not None),
        checkpointer=checkpointer,
    )
