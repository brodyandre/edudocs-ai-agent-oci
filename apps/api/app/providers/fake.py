from __future__ import annotations

from enum import Enum

from app.core.errors import (
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from app.providers.base import EvidencePayload, LLMResult, ProviderCitation


class FakeProviderMode(str, Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    EMPTY = "empty"
    INVALID_CITATION = "invalid_citation"
    UNGROUNDED = "ungrounded"


class FakeProvider:
    name = "fake"

    def __init__(self, mode: FakeProviderMode = FakeProviderMode.SUCCESS) -> None:
        self.mode = mode

    async def generate(
        self,
        question: str,
        evidences: list[EvidencePayload],
        system_prompt: str,
        timeout_seconds: float,
    ) -> LLMResult:
        del system_prompt, timeout_seconds
        if self.mode == FakeProviderMode.UNAVAILABLE:
            raise LLMProviderUnavailableError("Provedor falso indisponível.")
        if self.mode == FakeProviderMode.TIMEOUT:
            raise LLMProviderTimeoutError("Timeout simulado no provedor falso.")
        if self.mode == FakeProviderMode.RATE_LIMIT:
            raise LLMProviderRateLimitError("Rate limit simulado no provedor falso.")
        if self.mode == FakeProviderMode.EMPTY:
            return LLMResult(answer="", used_chunk_ids=[], citations=[])
        if self.mode == FakeProviderMode.UNGROUNDED:
            return LLMResult(
                answer="Resposta não fundamentada em evidências recuperadas.",
                used_chunk_ids=[],
                citations=[],
            )

        selected = evidences[:2]
        if not selected:
            return LLMResult(answer="", used_chunk_ids=[], citations=[])

        facts = []
        for evidence in selected:
            excerpt = evidence.text.split(". ")[0].strip()
            if excerpt and not excerpt.endswith("."):
                excerpt = f"{excerpt}."
            facts.append(excerpt)
        answer = (
            "Com base nos documentos da EduDocs Academy, "
            + " ".join(facts)
            + " Consulte as fontes indicadas para conferir documento, versão e página."
        )
        citations = [
            ProviderCitation(
                document_id=evidence.document_id,
                page=evidence.page_start,
                excerpt=evidence.text[:120],
            )
            for evidence in selected
        ]
        if self.mode == FakeProviderMode.INVALID_CITATION:
            citations.append(
                ProviderCitation(
                    document_id="documento-inexistente",
                    page=999,
                    excerpt="trecho inventado",
                )
            )
        return LLMResult(
            answer=answer,
            used_chunk_ids=[evidence.chunk_id for evidence in selected],
            citations=citations,
        )
