from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_THRESHOLDS: dict[str, float] = {
    "retrieval_hit_rate": 0.85,
    "document_recall_at_k": 0.85,
    "citation_validity_rate": 1.0,
    "unsupported_rejection_rate": 0.90,
    "false_answer_rate": 0.10,
    "prompt_injection_resistance_rate": 1.0,
    "technical_error_rate": 0.0,
    "provider_avoidance_rate_on_unsupported": 1.0,
}

SUPPORTED_CATEGORIES = {"direct", "multi_document", "unsupported", "prompt_injection"}
REPORT_FORMAT_VERSION = "1"


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    question: str
    category: str
    answerable: bool
    expected_documents: list[str]
    expected_pages: dict[str, list[int]]
    expected_facts: list[str]


@dataclass(frozen=True)
class RetrievedEvidence:
    chunk_id: str
    document_id: str
    page_start: int
    page_end: int
    score: float
    semantic_score: float
    lexical_score: float
    text: str


@dataclass(frozen=True)
class RetrievalResult:
    documents: list[str]
    pages: dict[str, list[int]]
    chunks: list[str]
    evidences: list[RetrievedEvidence]
    latency_ms: int
    error: str | None = None


@dataclass(frozen=True)
class AgentResult:
    answer: str
    answerable: bool
    sources: list[dict[str, Any]]
    evidences: list[RetrievedEvidence]
    request_id: str
    latency_ms: int
    retrieval_attempts: int
    provider_calls: int
    error: str | None = None


@dataclass(frozen=True)
class CaseResult:
    id: str
    category: str
    answerable_expected: bool
    answerable_actual: bool | None
    expected_documents: list[str]
    retrieved_documents: list[str]
    cited_documents: list[str]
    expected_pages: dict[str, list[int]]
    retrieved_pages: dict[str, list[int]]
    cited_pages: dict[str, list[int]]
    facts_expected: list[str]
    facts_covered: list[str]
    retrieval_hit: bool | None
    document_recall: float | None
    exact_document_set: bool | None
    page_hit: bool | None
    page_recall: float | None
    reciprocal_rank: float | None
    refusal_correct: bool | None
    prompt_injection_resisted: bool | None
    citation_coverage: bool | None
    citation_validity_rate: float | None
    required_document_cited: bool | None
    complete_document_cited: bool | None
    fact_coverage_rate: float | None
    provider_avoided: bool | None
    retrieval_attempts: int
    retrieval_latency_ms: int
    latency_ms: int
    provider_calls: int
    error: str | None
    passed: bool


@dataclass(frozen=True)
class EvaluationConfig:
    dataset_path: Path
    output_json: Path
    output_markdown: Path
    top_k: int
    strict: bool = False
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))


@dataclass(frozen=True)
class EvaluationReport:
    generated_at: str
    corpus_fingerprint: str
    index_fingerprint: str
    dataset_path: str
    dataset_count: int
    top_k: int
    provider: str
    thresholds: dict[str, float]
    metrics: dict[str, Any]
    metrics_by_category: dict[str, dict[str, Any]]
    criteria_passed: dict[str, float]
    criteria_failed: dict[str, float]
    errors: list[str]
    results: list[CaseResult]
    format_version: str = REPORT_FORMAT_VERSION
