from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.citations import validate_sources
from app.agents.prompts import SYSTEM_PROMPT
from app.agents.state import AgentState
from app.core.config import Settings
from app.documents.manifest import CorpusManifest
from app.ingestion.embeddings import EmbeddingProvider
from app.providers.base import EvidencePayload, LLMProvider
from app.retrieval.search import LocalIndex, SearchResult

INSUFFICIENT_MESSAGE = (
    "Não encontrei informações suficientes nos documentos disponíveis para responder com segurança."
)

INJECTION_PATTERNS = [
    re.compile(r"\bignore\b.+\b(regras|instruções|instrucoes|documentos)\b", re.IGNORECASE),
    re.compile(r"\brevele\b.+\b(prompt|segredo|chave|token)\b", re.IGNORECASE),
    re.compile(r"\buse conhecimento externo\b", re.IGNORECASE),
    re.compile(r"\bfinja\b.+\bsem evidências|sem evidencias\b", re.IGNORECASE),
]

STOPWORDS = {
    "como",
    "qual",
    "quais",
    "quando",
    "onde",
    "para",
    "pela",
    "pelo",
    "sobre",
    "com",
    "uma",
    "uns",
    "das",
    "dos",
    "que",
    "de",
    "do",
    "da",
    "e",
    "o",
    "a",
    "os",
    "as",
    "meu",
    "minha",
    "peço",
    "peco",
    "pedir",
    "solicito",
}

SYNONYMS = {
    "certificado": "certificados emissão segunda via validação",
    "diploma": "certificado certificados emissão validação",
    "reembolso": "cancelamento restituição financeiro arrependimento",
    "senha": "acesso recuperação credenciais",
    "privacidade": "dados retenção cookies menores",
    "matrícula": "matricula inscrição acesso curso",
}


@dataclass
class AgentDependencies:
    settings: Settings
    index: LocalIndex
    embedding_provider: EmbeddingProvider
    llm_provider: LLMProvider
    manifest: CorpusManifest
    evidence_store: dict[str, list[EvidencePayload]]


def normalize_question_text(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip())


def question_terms(question: str) -> set[str]:
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", question.lower())
    return {word for word in words if word not in STOPWORDS}


def sanitize_query(question: str) -> str:
    query = question
    for pattern in INJECTION_PATTERNS:
        query = pattern.sub(" ", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query or question


def result_to_evidence(result: SearchResult) -> EvidencePayload:
    metadata = result.metadata
    return EvidencePayload(
        chunk_id=result.chunk_id,
        document_id=str(metadata["document_id"]),
        document_title=str(metadata["document_title"]),
        document_version=str(metadata["document_version"]),
        page_start=int(metadata["page_start"]),
        page_end=int(metadata["page_end"]),
        section=str(metadata["section"]) if metadata.get("section") else None,
        text=result.text,
        semantic_score=result.semantic_score,
        lexical_score=result.lexical_score,
        final_score=result.score,
    )


def dedupe_and_diversify(results: list[SearchResult], limit: int) -> list[EvidencePayload]:
    evidences: list[EvidencePayload] = []
    seen_chunks: set[str] = set()
    seen_pages: set[tuple[str, int]] = set()

    for result in results:
        if result.chunk_id in seen_chunks:
            continue
        evidence = result_to_evidence(result)
        page_key = (evidence.document_id, evidence.page_start)
        if page_key in seen_pages and len(evidences) >= 2:
            continue
        seen_chunks.add(result.chunk_id)
        seen_pages.add(page_key)
        evidences.append(evidence)
        if len(evidences) >= limit:
            break

    if len(evidences) < limit:
        for result in results:
            if result.chunk_id in seen_chunks:
                continue
            evidences.append(result_to_evidence(result))
            seen_chunks.add(result.chunk_id)
            if len(evidences) >= limit:
                break
    return evidences


def validate_question(state: AgentState, deps: AgentDependencies) -> AgentState:
    normalized = normalize_question_text(state["question"])
    if len(normalized) < deps.settings.min_question_length:
        return {"error": "Pergunta vazia ou curta demais.", "answerable": False}
    if len(normalized) > deps.settings.max_question_length:
        return {"error": "Pergunta acima do limite configurado.", "answerable": False}
    return {"normalized_question": normalized, "retrieval_attempt": 0, "answerable": False}


def prepare_query(state: AgentState, deps: AgentDependencies) -> AgentState:
    del deps
    return {"retrieval_query": sanitize_query(state["normalized_question"])}


def retrieve_evidence(state: AgentState, deps: AgentDependencies) -> AgentState:
    results = deps.index.search(
        state["retrieval_query"],
        deps.embedding_provider,
        top_k=max(deps.settings.chat_top_k, deps.settings.evidence_limit * 2),
        batch_size=deps.settings.batch_size,
    )
    evidences = dedupe_and_diversify(results, deps.settings.evidence_limit)
    total = 0
    clipped: list[EvidencePayload] = []
    for evidence in evidences:
        if total + len(evidence.text) > deps.settings.max_context_chars:
            break
        clipped.append(evidence)
        total += len(evidence.text)
    deps.evidence_store[state["request_id"]] = clipped
    return {
        "retrieved_chunks": [evidence.chunk_id for evidence in clipped],
        "retrieval_attempt": int(state.get("retrieval_attempt", 0)) + 1,
    }


def evaluate_sufficiency(state: AgentState, deps: AgentDependencies) -> AgentState:
    evidences = deps.evidence_store.get(state["request_id"], [])
    if not evidences:
        return {"sufficient_context": False}
    relevant = [item for item in evidences if item.final_score >= deps.settings.min_retrieval_score]
    if not relevant:
        return {"sufficient_context": False}

    terms = question_terms(
        state["retrieval_query"]
        if int(state.get("retrieval_attempt", 0)) > 1
        else state["normalized_question"]
    )
    joined = " ".join(item.text.lower() for item in relevant)
    term_hits = {term for term in terms if term in joined}
    if terms and len(term_hits) / len(terms) < 0.25:
        return {"sufficient_context": False}

    asks_multi = any(
        marker in state["normalized_question"].lower()
        for marker in ["dois documentos", "entre", "e o", "e a", "compare", "consistente"]
    )
    document_count = len({item.document_id for item in relevant})
    if asks_multi and document_count < 2:
        return {"sufficient_context": False}
    deps.evidence_store[state["request_id"]] = relevant[: deps.settings.evidence_limit]
    return {"sufficient_context": True}


def reformulate_query(state: AgentState, deps: AgentDependencies) -> AgentState:
    del deps
    query = state["retrieval_query"]
    additions = [value for key, value in SYNONYMS.items() if key in query.lower()]
    expanded = f"{query} {' '.join(additions)}".strip()
    return {"retrieval_query": expanded}


async def generate_answer(state: AgentState, deps: AgentDependencies) -> AgentState:
    evidences = deps.evidence_store.get(state["request_id"], [])
    allowed = set(state.get("retrieved_chunks", []))
    selected = [evidence for evidence in evidences if evidence.chunk_id in allowed]
    result = await deps.llm_provider.generate(
        question=state["normalized_question"],
        evidences=selected,
        system_prompt=SYSTEM_PROMPT,
        timeout_seconds=deps.settings.llm_timeout_seconds,
    )
    answer = normalize_question_text(result.answer)
    if not answer:
        return {
            "answerable": False,
            "generated_answer": INSUFFICIENT_MESSAGE,
            "provider_result": result,
        }
    return {"answerable": True, "generated_answer": answer, "provider_result": result}


def validate_citations_node(state: AgentState, deps: AgentDependencies) -> AgentState:
    evidences = deps.evidence_store.get(state["request_id"], [])
    allowed = set(state.get("retrieved_chunks", []))
    sources = validate_sources(
        state.get("provider_result"),
        [evidence for evidence in evidences if evidence.chunk_id in allowed],
        deps.manifest,
    )
    if not sources:
        return {
            "answerable": False,
            "generated_answer": INSUFFICIENT_MESSAGE,
            "validated_sources": [],
        }
    return {"validated_sources": sources, "answerable": True}


def insufficient_evidence(state: AgentState, deps: AgentDependencies) -> AgentState:
    del state, deps
    return {
        "answerable": False,
        "generated_answer": INSUFFICIENT_MESSAGE,
        "validated_sources": [],
    }
