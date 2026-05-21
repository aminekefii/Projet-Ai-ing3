from langchain_community.tools import ArxivQueryRun, DuckDuckGoSearchRun, WikipediaQueryRun
from langchain_community.utilities import ArxivAPIWrapper, WikipediaAPIWrapper
from langchain_core.tools import tool
from langchain_experimental.tools import PythonREPLTool

from .rag import format_results

_ddg = DuckDuckGoSearchRun()
_wiki = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=2500)
)
_arxiv = ArxivQueryRun(
    api_wrapper=ArxivAPIWrapper(top_k_results=3, doc_content_chars_max=2500)
)
_python = PythonREPLTool()


def _safe(fn, query: str) -> str:
    try:
        result = fn(query)
        return result if result else "No results found. Try a different query."
    except Exception as e:
        return f"Tool error: {type(e).__name__}: {e}. Try a different query or tool."


@tool
def web_search(query: str) -> str:
    """Search the live web via DuckDuckGo. Use for current events, news,
    recent papers, or anything that may have changed recently.
    Input: a search query string."""
    return _safe(_ddg.run, query)


@tool
def wikipedia(query: str) -> str:
    """Look up encyclopedic background on a topic from Wikipedia.
    Best for established facts, definitions, history, biographies.
    Input: a concise article title or topic."""
    return _safe(_wiki.run, query)


@tool
def arxiv(query: str) -> str:
    """Search academic papers on arXiv. Best for scientific or technical
    questions where peer-reviewed or pre-print evidence is needed.
    Input: a search query (keywords or a paper title)."""
    return _safe(_arxiv.run, query)


@tool
def python_repl(code: str) -> str:
    """Execute Python code in a sandboxed REPL. Use for math, unit conversions,
    string manipulation, or quick data processing.
    Input: valid Python code. Use print() to see results."""
    return _safe(_python.run, code)


def _make_document_search(vectorstore):
    """Closure-based tool: searches whichever vectorstore is currently loaded."""

    @tool
    def document_search(query: str) -> str:
        """Search the student's uploaded readings (PDFs, notes, primary sources) for passages
        relevant to a topic or section. Use whenever the student has provided their own
        materials and the current task could benefit from them — this is the case for
        every section of a paper when documents are uploaded. Returns passages with
        filename and page number for citation.
        Input: a natural-language query, typically a section title + key terms."""
        try:
            results = vectorstore.similarity_search(query, k=4)
            return format_results(results)
        except Exception as e:
            return f"Tool error: {type(e).__name__}: {e}"

    return document_search


def build_tools(vectorstore=None):
    """Return the agent's tool list. Adds document_search if a vector store is provided."""
    tools = [web_search, wikipedia, arxiv, python_repl]
    if vectorstore is not None:
        tools.append(_make_document_search(vectorstore))
    return tools
