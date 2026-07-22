from __future__ import annotations

from typing import TypedDict

from app.providers.base import LLMResult


class AgentState(TypedDict, total=False):
    question: str
    normalized_question: str
    retrieval_query: str
    retrieval_attempt: int
    retrieved_chunks: list[str]
    sufficient_context: bool
    generated_answer: str
    provider_result: LLMResult | None
    validated_sources: list[dict[str, object]]
    answerable: bool
    error: str | None
    request_id: str
