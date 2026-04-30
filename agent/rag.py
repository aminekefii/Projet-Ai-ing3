"""Retrieval-Augmented Generation utilities — load, chunk, embed, index."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import pypdf
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # ~33 MB, ONNX, fast on CPU
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

_embeddings: FastEmbedEmbeddings | None = None


def get_embeddings() -> FastEmbedEmbeddings:
    """Singleton embedder. First call downloads the ONNX model (~33 MB)."""
    global _embeddings
    if _embeddings is None:
        _embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def load_pdf(data: bytes, filename: str) -> list[Document]:
    """Extract one Document per non-empty page."""
    reader = pypdf.PdfReader(BytesIO(data))
    docs: list[Document] = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": filename, "page": i + 1},
                )
            )
    return docs


def load_txt(data: bytes, filename: str) -> list[Document]:
    text = data.decode("utf-8", errors="ignore").strip()
    if not text:
        return []
    return [Document(page_content=text, metadata={"source": filename})]


def chunk_documents(docs: Iterable[Document]) -> list[Document]:
    """Recursive splitting on paragraph/sentence boundaries with overlap."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(list(docs))


def index_uploaded_files(uploaded_files) -> tuple[FAISS | None, list[tuple[str, int]]]:
    """Take Streamlit UploadedFile objects, return (vectorstore, [(filename, n_chunks)]).

    Returns (None, []) if no usable content was extracted.
    """
    all_docs: list[Document] = []
    per_file_pages: list[tuple[str, int]] = []

    for f in uploaded_files:
        data = f.getvalue()
        name = f.name
        lower = name.lower()
        if lower.endswith(".pdf"):
            docs = load_pdf(data, name)
        elif lower.endswith(".txt"):
            docs = load_txt(data, name)
        else:
            continue
        if docs:
            all_docs.extend(docs)
            per_file_pages.append((name, len(docs)))

    if not all_docs:
        return None, []

    chunks = chunk_documents(all_docs)
    summary = [
        (name, sum(1 for c in chunks if c.metadata.get("source") == name))
        for name, _ in per_file_pages
    ]
    vectorstore = FAISS.from_documents(chunks, get_embeddings())
    return vectorstore, summary


def format_results(results: list[Document]) -> str:
    """Format similarity_search results as a citation-friendly string."""
    if not results:
        return "No relevant passages found in the uploaded documents."
    blocks = []
    for i, doc in enumerate(results, 1):
        src = doc.metadata.get("source", "?")
        page = doc.metadata.get("page")
        cite = f"[{i}] {src}" + (f" (page {page})" if page else "")
        blocks.append(f"{cite}\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(blocks)
