from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.agents.service import RAGAgentService
from app.core.config import Settings
from app.documents.manifest import corpus_fingerprint, enabled_documents, load_manifest
from app.evaluation.dataset import load_evaluation_cases
from app.evaluation.metrics import (
    covered_facts,
    global_metrics,
    metrics_by_category,
    prompt_injection_resisted,
)
from app.evaluation.models import (
    AgentResult,
    CaseResult,
    EvaluationConfig,
    EvaluationReport,
    RetrievalResult,
    RetrievedEvidence,
)
from app.ingestion.embeddings import FakeEmbeddingProvider
from app.ingestion.index import active_index_dir, validate_index
from app.providers.fake import FakeProvider, FakeProviderMode
from app.retrieval.search import LocalIndex, SearchResult


class CountingFakeProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__(FakeProviderMode.SUCCESS)
        self.calls = 0

    async def generate(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        self.calls += 1
        return await super().generate(*args, **kwargs)


def run_evaluation(settings: Settings, config: EvaluationConfig) -> EvaluationReport:
    cases = load_evaluation_cases(config.dataset_path, settings)
    manifest = load_manifest(settings.resolved_manifest_path, settings.repo_root)
    index_manifest = validate_index(
        active_index_dir(settings.resolved_index_dir),
        settings=settings,
    )
    index = LocalIndex.load(settings)
    embedding_provider = FakeEmbeddingProvider(dimension=settings.fake_embedding_dimension)

    results = [
        _run_case(case, settings, index, embedding_provider, manifest, config.top_k)
        for case in cases
    ]
    metrics = global_metrics(results)
    criteria_passed, criteria_failed = evaluate_criteria(metrics, config.thresholds)
    return EvaluationReport(
        generated_at=datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        corpus_fingerprint=corpus_fingerprint(manifest),
        index_fingerprint=str(index_manifest["config_fingerprint"]),
        dataset_path=_display_path(config.dataset_path, settings.repo_root),
        dataset_count=len(cases),
        top_k=config.top_k,
        provider="fake",
        thresholds=config.thresholds,
        metrics=metrics,
        metrics_by_category=metrics_by_category(results),
        criteria_passed=criteria_passed,
        criteria_failed=criteria_failed,
        errors=[result.error for result in results if result.error],
        results=results,
    )


def evaluate_criteria(
    metrics: dict[str, Any],
    thresholds: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    passed: dict[str, float] = {}
    failed: dict[str, float] = {}
    for name, threshold in thresholds.items():
        value = metrics.get(name)
        if value is None:
            failed[name] = threshold
            continue
        is_maximum = name in {"false_answer_rate", "technical_error_rate"}
        ok = value <= threshold if is_maximum else value >= threshold
        target = passed if ok else failed
        target[name] = float(value)
    return passed, failed


def _display_path(path, repo_root) -> str:  # type: ignore[no-untyped-def]
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _run_case(
    case,
    settings: Settings,
    index: LocalIndex,
    embedding_provider: FakeEmbeddingProvider,
    manifest,
    top_k: int,
) -> CaseResult:
    retrieval = _run_retrieval(case.question, settings, index, embedding_provider, top_k)
    provider = CountingFakeProvider()
    service = RAGAgentService(settings, llm_provider=provider)
    agent = _run_agent(service, provider, case.question, case.id)
    return _build_case_result(case, retrieval, agent, manifest)


def _run_retrieval(
    question: str,
    settings: Settings,
    index: LocalIndex,
    embedding_provider: FakeEmbeddingProvider,
    top_k: int,
) -> RetrievalResult:
    started = time.perf_counter()
    try:
        results = index.search(
            question,
            embedding_provider,
            top_k=top_k,
            batch_size=settings.batch_size,
        )
    except Exception as exc:  # pragma: no cover - infraestrutura defensiva
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return RetrievalResult([], {}, [], [], latency_ms, error=exc.__class__.__name__)
    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    evidences = [_to_evidence(result) for result in results]
    return RetrievalResult(
        documents=_ordered_unique(evidence.document_id for evidence in evidences),
        pages=_pages_by_document(evidences),
        chunks=[evidence.chunk_id for evidence in evidences],
        evidences=evidences,
        latency_ms=latency_ms,
    )


def _run_agent(
    service: RAGAgentService,
    provider: CountingFakeProvider,
    question: str,
    request_id: str,
) -> AgentResult:
    started = time.perf_counter()
    retrieval_calls = 0
    original_search = service.deps.index.search

    def counting_search(*args: object, **kwargs: object) -> list[SearchResult]:
        nonlocal retrieval_calls
        retrieval_calls += 1
        return original_search(*args, **kwargs)

    service.deps.index.search = counting_search  # type: ignore[method-assign]
    try:
        result = _run_async_answer(service, question, request_id)
    except Exception as exc:  # pragma: no cover - infraestrutura defensiva
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return AgentResult(
            answer="",
            answerable=False,
            sources=[],
            evidences=[],
            request_id=request_id,
            latency_ms=latency_ms,
            retrieval_attempts=retrieval_calls,
            provider_calls=provider.calls,
            error=exc.__class__.__name__,
        )
    finally:
        service.deps.index.search = original_search  # type: ignore[method-assign]

    agent_evidences = [
        RetrievedEvidence(
            chunk_id=evidence.chunk_id,
            document_id=evidence.document_id,
            page_start=evidence.page_start,
            page_end=evidence.page_end,
            score=evidence.final_score,
            semantic_score=evidence.semantic_score,
            lexical_score=evidence.lexical_score,
            text=evidence.text,
        )
        for evidence in service.evidence_store.get(request_id, [])
    ]
    return AgentResult(
        answer=result.answer,
        answerable=result.answerable,
        sources=result.sources,
        evidences=agent_evidences,
        request_id=result.request_id,
        latency_ms=result.latency_ms,
        retrieval_attempts=retrieval_calls,
        provider_calls=provider.calls,
    )


def _run_async_answer(service: RAGAgentService, question: str, request_id: str):
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(service.answer(question, request_id))

    raise RuntimeError("Avaliação deve ser executada fora de um event loop ativo.")


def _build_case_result(
    case,
    retrieval: RetrievalResult,
    agent: AgentResult,
    manifest,
) -> CaseResult:
    expected_docs = set(case.expected_documents)
    retrieved_docs = set(retrieval.documents)
    cited_docs = _ordered_unique(str(source.get("document_id", "")) for source in agent.sources)
    cited_pages = _cited_pages(agent.sources)

    expected_pages = {
        document: set(pages) for document, pages in case.expected_pages.items()
    }
    retrieved_pages = {document: set(pages) for document, pages in retrieval.pages.items()}
    expected_page_pairs = {
        (document, page)
        for document, pages in expected_pages.items()
        for page in pages
    }
    retrieved_page_pairs = {
        (document, page)
        for document, pages in retrieved_pages.items()
        for page in pages
    }

    facts_covered = (
        covered_facts(agent.answer, case.expected_facts)
        if case.answerable and not agent.error
        else []
    )
    citation_validity = _citation_validity(agent.sources, agent.evidences, manifest)
    answerable_actual = None if agent.error else agent.answerable
    retrieval_hit = bool(expected_docs & retrieved_docs) if case.answerable else None
    document_recall = (
        len(expected_docs & retrieved_docs) / len(expected_docs) if expected_docs else None
    )
    exact_document_set = expected_docs <= retrieved_docs if expected_docs else None
    page_hit = (
        bool(expected_page_pairs & retrieved_page_pairs) if expected_page_pairs else None
    )
    page_recall = (
        len(expected_page_pairs & retrieved_page_pairs) / len(expected_page_pairs)
        if expected_page_pairs
        else None
    )
    reciprocal_rank = (
        _reciprocal_rank(retrieval.documents, expected_docs) if expected_docs else None
    )
    refusal_correct = (answerable_actual is False) if not case.answerable else None
    prompt_resisted = (
        prompt_injection_resisted(agent.answer, bool(answerable_actual))
        if case.category == "prompt_injection" and answerable_actual is not None
        else None
    )
    citation_coverage = bool(agent.sources) if answerable_actual is True else None
    required_document_cited = (
        bool(expected_docs & set(cited_docs))
        if expected_docs and answerable_actual is True
        else None
    )
    complete_document_cited = (
        expected_docs <= set(cited_docs)
        if case.category == "multi_document" and answerable_actual is True
        else None
    )
    fact_rate = (
        len(facts_covered) / len(case.expected_facts)
        if case.answerable and case.expected_facts
        else None
    )
    provider_avoided = (agent.provider_calls == 0) if not case.answerable else None
    passed = all(
        value
        for value in [
            agent.error is None,
            answerable_actual == case.answerable,
            not case.answerable or retrieval_hit,
            answerable_actual is not True or citation_coverage,
            answerable_actual is not True or citation_validity == 1.0,
            case.category != "prompt_injection" or prompt_resisted,
        ]
    )
    return CaseResult(
        id=case.id,
        category=case.category,
        answerable_expected=case.answerable,
        answerable_actual=answerable_actual,
        expected_documents=case.expected_documents,
        retrieved_documents=retrieval.documents,
        cited_documents=cited_docs,
        expected_pages={doc: list(pages) for doc, pages in case.expected_pages.items()},
        retrieved_pages=retrieval.pages,
        cited_pages=cited_pages,
        facts_expected=case.expected_facts,
        facts_covered=facts_covered,
        retrieval_hit=retrieval_hit,
        document_recall=document_recall,
        exact_document_set=exact_document_set,
        page_hit=page_hit,
        page_recall=page_recall,
        reciprocal_rank=reciprocal_rank,
        refusal_correct=refusal_correct,
        prompt_injection_resisted=prompt_resisted,
        citation_coverage=citation_coverage,
        citation_validity_rate=citation_validity if answerable_actual is True else None,
        required_document_cited=required_document_cited,
        complete_document_cited=complete_document_cited,
        fact_coverage_rate=fact_rate,
        provider_avoided=provider_avoided,
        retrieval_attempts=agent.retrieval_attempts,
        retrieval_latency_ms=retrieval.latency_ms,
        latency_ms=agent.latency_ms,
        provider_calls=agent.provider_calls,
        error=agent.error or retrieval.error,
        passed=passed,
    )


def _to_evidence(result: SearchResult) -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk_id=result.chunk_id,
        document_id=str(result.metadata["document_id"]),
        page_start=int(result.metadata["page_start"]),
        page_end=int(result.metadata["page_end"]),
        score=result.score,
        semantic_score=result.semantic_score,
        lexical_score=result.lexical_score,
        text=result.text,
    )


def _pages_by_document(evidences: list[RetrievedEvidence]) -> dict[str, list[int]]:
    pages: dict[str, set[int]] = {}
    for evidence in evidences:
        pages.setdefault(evidence.document_id, set()).update(
            range(evidence.page_start, evidence.page_end + 1)
        )
    return {document: sorted(values) for document, values in sorted(pages.items())}


def _cited_pages(sources: list[dict[str, Any]]) -> dict[str, list[int]]:
    pages: dict[str, set[int]] = {}
    for source in sources:
        document = str(source.get("document_id", ""))
        page = source.get("page")
        if document and isinstance(page, int):
            pages.setdefault(document, set()).add(page)
    return {document: sorted(values) for document, values in sorted(pages.items())}


def _citation_validity(
    sources: list[dict[str, Any]],
    evidences: list[RetrievedEvidence],
    manifest,
) -> float | None:
    if not sources:
        return None
    enabled = {document.id: document for document in enabled_documents(manifest)}
    valid = 0
    for source in sources:
        document_id = str(source.get("document_id", ""))
        version = str(source.get("version", ""))
        page = source.get("page")
        excerpt = " ".join(str(source.get("excerpt", "")).split())
        document = enabled.get(document_id)
        if document is None or version != document.version or not isinstance(page, int):
            continue
        excerpt_prefix = excerpt.replace("…", "")
        if not any(
            evidence.document_id == document_id
            and evidence.page_start <= page <= evidence.page_end
            and excerpt_prefix
            and excerpt_prefix in " ".join(evidence.text.split())
            for evidence in evidences
        ):
            continue
        valid += 1
    return valid / len(sources)


def _reciprocal_rank(documents: list[str], expected_docs: set[str]) -> float | None:
    for index, document in enumerate(documents, start=1):
        if document in expected_docs:
            return 1 / index
    return 0.0


def _ordered_unique(values: Any) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered
