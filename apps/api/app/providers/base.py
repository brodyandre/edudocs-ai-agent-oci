from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderCitation:
    document_id: str
    page: int
    excerpt: str


@dataclass(frozen=True)
class LLMResult:
    answer: str
    used_chunk_ids: list[str]
    citations: list[ProviderCitation]


@dataclass(frozen=True)
class EvidencePayload:
    chunk_id: str
    document_id: str
    document_title: str
    document_version: str
    page_start: int
    page_end: int
    section: str | None
    text: str
    semantic_score: float
    lexical_score: float
    final_score: float


class LLMProvider(Protocol):
    name: str

    async def generate(
        self,
        question: str,
        evidences: list[EvidencePayload],
        system_prompt: str,
        timeout_seconds: float,
    ) -> LLMResult:
        """Gera resposta com base somente nas evidências recebidas."""
