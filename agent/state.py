"""Shared graph state and validated models for the multi-agent research-paper system."""
from __future__ import annotations

from typing import Literal, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class Section(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)
    target_words: int = 500


class Source(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    url: Optional[str] = None
    snippet: str = ""
    origin_tool: Literal["web_search", "wikipedia", "arxiv", "document_search"]
    covers_sections: list[str] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    section: str
    kind: Literal["missing_citation", "weak_argument", "off_topic", "repetition"]
    suggestion: str


class ReviewReport(BaseModel):
    issues: list[ReviewIssue] = Field(default_factory=list)
    verdict: Literal["pass", "revise"]


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0
    total: int = 0
    budget: int = 200_000
    warning: bool = False
    halt: bool = False


class PaperState(TypedDict, total=False):
    topic: str
    mode: Literal["survey", "empirical", "term"]
    outline: list[Section]
    user_data: list[Document]
    sources: list[Source]
    draft: dict[str, str]
    review: Optional[ReviewReport]
    revision_count: int
    token_usage: TokenUsage
    messages: list[BaseMessage]
    final_output: Optional[str]
    forced_review_issues: list  # ReviewIssue[] — populated by drafter, consumed by reviewer
    analysis_results: dict  # {stat_name: value} — populated by data_analyzer
    tool_calls: list  # [{tool, input}, ...] — populated by researcher for UI trace
