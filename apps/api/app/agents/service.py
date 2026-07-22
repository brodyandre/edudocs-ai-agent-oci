from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from app.agents.graph import build_graph
from app.agents.nodes import INSUFFICIENT_MESSAGE, AgentDependencies
from app.agents.state import AgentState
from app.core.config import Settings
from app.documents.manifest import load_manifest
from app.ingestion.provider_factory import create_embedding_provider
from app.providers.base import EvidencePayload, LLMProvider
from app.providers.factory import create_llm_provider
from app.retrieval.search import LocalIndex

LOGGER = logging.getLogger("edudocs.api.chat")


@dataclass(frozen=True)
class ChatResult:
    answer: str
    answerable: bool
    sources: list[dict[str, object]]
    request_id: str
    latency_ms: int
    evidence_count: int


def generate_request_id() -> str:
    return str(uuid.uuid4())


def sanitize_request_id(value: str | None) -> str:
    if value is None:
        return generate_request_id()
    candidate = value.strip()
    if not candidate or len(candidate) > 80:
        return generate_request_id()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:")
    if any(char not in allowed for char in candidate):
        return generate_request_id()
    return candidate


class RAGAgentService:
    def __init__(self, settings: Settings, llm_provider: LLMProvider | None = None) -> None:
        self.settings = settings
        self.manifest = load_manifest(settings.resolved_manifest_path, settings.repo_root)
        self.index = LocalIndex.load(settings)
        self.embedding_provider = create_embedding_provider(settings)
        self.llm_provider = llm_provider or create_llm_provider(settings)
        self.evidence_store: dict[str, list[EvidencePayload]] = {}
        self.deps = AgentDependencies(
            settings=settings,
            index=self.index,
            embedding_provider=self.embedding_provider,
            llm_provider=self.llm_provider,
            manifest=self.manifest,
            evidence_store=self.evidence_store,
        )
        self.graph = build_graph(self.deps)

    async def answer(self, question: str, request_id: str) -> ChatResult:
        started = time.perf_counter()
        state: AgentState = {
            "question": question,
            "request_id": request_id,
            "retrieval_attempt": 0,
            "retrieved_chunks": [],
            "validated_sources": [],
            "answerable": False,
        }
        final_state = self.graph.invoke(
            state,
            {"recursion_limit": (self.settings.max_retrieval_attempts * 4) + 8},
        )
        answerable = bool(final_state.get("answerable", False))
        answer = str(final_state.get("generated_answer") or INSUFFICIENT_MESSAGE)
        sources = list(final_state.get("validated_sources", [])) if answerable else []
        evidence_count = len(self.evidence_store.get(request_id, []))
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        LOGGER.info(
            "chat_request",
            extra={
                "request_id": request_id,
                "route": "/api/chat",
                "status": "ok",
                "latency_ms": latency_ms,
                "provider": self.llm_provider.name,
                "evidence_count": evidence_count,
                "answerable": answerable,
                "error_type": None,
            },
        )
        return ChatResult(
            answer=answer,
            answerable=answerable,
            sources=sources,
            request_id=request_id,
            latency_ms=latency_ms,
            evidence_count=evidence_count,
        )
