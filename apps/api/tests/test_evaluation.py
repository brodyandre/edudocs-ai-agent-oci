from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.agents.service import RAGAgentService
from app.core.config import Settings
from app.evaluation.cli import main as evaluation_cli
from app.evaluation.dataset import EvaluationDatasetError, load_evaluation_cases
from app.evaluation.metrics import (
    agent_metrics,
    covered_facts,
    metrics_by_category,
    percentile,
    prompt_injection_resisted,
    retrieval_metrics,
)
from app.evaluation.models import CaseResult, EvaluationConfig
from app.evaluation.report import report_to_dict, write_json_report, write_markdown_report
from app.evaluation.runner import run_evaluation


@pytest.fixture()
def repo_settings() -> Settings:
    return Settings(llm_provider="fake", embedding_provider="fake")


@pytest.fixture()
def dataset_path(repo_settings: Settings) -> Path:
    return repo_settings.repo_root / "corpus/evaluation/questions.json"


@pytest.fixture()
def eval_config(repo_settings: Settings, tmp_path: Path, dataset_path: Path) -> EvaluationConfig:
    return EvaluationConfig(
        dataset_path=dataset_path,
        output_json=tmp_path / "latest.json",
        output_markdown=tmp_path / "report.md",
        top_k=repo_settings.chat_top_k,
    )


def mutate_dataset(source: Path, target: Path, mutator) -> Path:  # type: ignore[no-untyped-def]
    data = json.loads(source.read_text(encoding="utf-8"))
    mutator(data)
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target


def make_case(
    *,
    case_id: str = "case-1",
    category: str = "direct",
    expected: bool = True,
    actual: bool | None = True,
    expected_docs: list[str] | None = None,
    retrieved_docs: list[str] | None = None,
    cited_docs: list[str] | None = None,
    expected_pages: dict[str, list[int]] | None = None,
    retrieved_pages: dict[str, list[int]] | None = None,
    cited_pages: dict[str, list[int]] | None = None,
    facts_expected: list[str] | None = None,
    facts_covered: list[str] | None = None,
    provider_calls: int = 1,
    error: str | None = None,
    latency_ms: int = 10,
) -> CaseResult:
    expected_docs = expected_docs if expected_docs is not None else ["doc-a"]
    retrieved_docs = retrieved_docs if retrieved_docs is not None else ["doc-a"]
    cited_docs = cited_docs if cited_docs is not None else ["doc-a"]
    expected_pages = expected_pages if expected_pages is not None else {"doc-a": [1]}
    retrieved_pages = retrieved_pages if retrieved_pages is not None else {"doc-a": [1]}
    cited_pages = cited_pages if cited_pages is not None else {"doc-a": [1]}
    facts_expected = facts_expected if facts_expected is not None else ["Fato esperado."]
    facts_covered = facts_covered if facts_covered is not None else ["Fato esperado."]
    expected_doc_set = set(expected_docs)
    retrieved_doc_set = set(retrieved_docs)
    expected_page_pairs = {
        (document, page) for document, pages in expected_pages.items() for page in pages
    }
    retrieved_page_pairs = {
        (document, page) for document, pages in retrieved_pages.items() for page in pages
    }
    answerable_true = actual is True
    return CaseResult(
        id=case_id,
        category=category,
        answerable_expected=expected,
        answerable_actual=actual,
        expected_documents=expected_docs,
        retrieved_documents=retrieved_docs,
        cited_documents=cited_docs,
        expected_pages=expected_pages,
        retrieved_pages=retrieved_pages,
        cited_pages=cited_pages,
        facts_expected=facts_expected,
        facts_covered=facts_covered,
        retrieval_hit=bool(expected_doc_set & retrieved_doc_set) if expected else None,
        document_recall=(
            len(expected_doc_set & retrieved_doc_set) / len(expected_doc_set)
            if expected_doc_set
            else None
        ),
        exact_document_set=expected_doc_set <= retrieved_doc_set if expected_doc_set else None,
        page_hit=bool(expected_page_pairs & retrieved_page_pairs) if expected_page_pairs else None,
        page_recall=(
            len(expected_page_pairs & retrieved_page_pairs) / len(expected_page_pairs)
            if expected_page_pairs
            else None
        ),
        reciprocal_rank=1.0 if expected and expected_doc_set & retrieved_doc_set else None,
        refusal_correct=(actual is False) if not expected else None,
        prompt_injection_resisted=(
            prompt_injection_resisted("Não encontrei informações suficientes.", bool(actual))
            if category == "prompt_injection"
            else None
        ),
        citation_coverage=bool(cited_docs) if answerable_true else None,
        citation_validity_rate=1.0 if answerable_true and cited_docs else None,
        required_document_cited=(
            bool(expected_doc_set & set(cited_docs)) if expected and answerable_true else None
        ),
        complete_document_cited=(
            expected_doc_set <= set(cited_docs)
            if category == "multi_document" and answerable_true
            else None
        ),
        fact_coverage_rate=(
            len(facts_covered) / len(facts_expected) if expected and facts_expected else None
        ),
        provider_avoided=(provider_calls == 0) if not expected else None,
        retrieval_attempts=1 if retrieved_docs else 0,
        retrieval_latency_ms=2,
        latency_ms=latency_ms,
        provider_calls=provider_calls,
        error=error,
        passed=error is None and actual == expected,
    )


def test_dataset_valido(repo_settings: Settings, dataset_path: Path) -> None:
    cases = load_evaluation_cases(dataset_path, repo_settings)
    assert len(cases) == 28
    assert cases[0].id == "direct-001"


def test_dataset_json_invalido(repo_settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "questions.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(EvaluationDatasetError, match="JSON inválido"):
        load_evaluation_cases(path, repo_settings)


def test_dataset_id_duplicado(repo_settings: Settings, dataset_path: Path, tmp_path: Path) -> None:
    path = mutate_dataset(
        dataset_path,
        tmp_path / "questions.json",
        lambda data: data.append(data[0]),
    )
    with pytest.raises(EvaluationDatasetError, match="duplicado"):
        load_evaluation_cases(path, repo_settings)


def test_dataset_categoria_invalida(
    repo_settings: Settings,
    dataset_path: Path,
    tmp_path: Path,
) -> None:
    path = mutate_dataset(
        dataset_path,
        tmp_path / "questions.json",
        lambda data: data[0].update(category="x"),
    )
    with pytest.raises(EvaluationDatasetError, match="Categoria inválida"):
        load_evaluation_cases(path, repo_settings)


def test_dataset_documento_esperado_inexistente(
    repo_settings: Settings,
    dataset_path: Path,
    tmp_path: Path,
) -> None:
    path = mutate_dataset(
        dataset_path,
        tmp_path / "questions.json",
        lambda data: data[0].update(expected_documents=["nao-existe"]),
    )
    with pytest.raises(EvaluationDatasetError, match="Documento esperado inexistente"):
        load_evaluation_cases(path, repo_settings)


def test_dataset_pagina_esperada_inexistente(
    repo_settings: Settings,
    dataset_path: Path,
    tmp_path: Path,
) -> None:
    def mutate(data: list[dict[str, Any]]) -> None:
        data[0]["expected_pages"] = {"regulamento-do-estudante": [999]}

    path = mutate_dataset(dataset_path, tmp_path / "questions.json", mutate)
    with pytest.raises(EvaluationDatasetError, match="Página esperada inexistente"):
        load_evaluation_cases(path, repo_settings)


def test_dataset_incoerencia_answerable_categoria(
    repo_settings: Settings,
    dataset_path: Path,
    tmp_path: Path,
) -> None:
    path = mutate_dataset(
        dataset_path,
        tmp_path / "questions.json",
        lambda data: data[0].update(answerable=False),
    )
    with pytest.raises(EvaluationDatasetError, match="respondível"):
        load_evaluation_cases(path, repo_settings)


def test_retrieval_hit_rate() -> None:
    metrics = retrieval_metrics([make_case(), make_case(retrieved_docs=["x"])])
    assert metrics["retrieval_hit_rate"] == 0.5


def test_document_recall_at_k() -> None:
    metrics = retrieval_metrics(
        [
            make_case(expected_docs=["a", "b"], retrieved_docs=["a"]),
            make_case(expected_docs=["a"], retrieved_docs=["a"]),
        ]
    )
    assert metrics["document_recall_at_k"] == 0.75


def test_exact_document_set_rate() -> None:
    metrics = retrieval_metrics(
        [make_case(), make_case(expected_docs=["a", "b"], retrieved_docs=["a"])]
    )
    assert metrics["exact_document_set_rate"] == 0.5


def test_page_hit_rate() -> None:
    metrics = retrieval_metrics(
        [
            make_case(expected_pages={"a": [1]}, retrieved_pages={"a": [2]}),
            make_case(expected_pages={"a": [1]}, retrieved_pages={"a": [1]}),
        ]
    )
    assert metrics["page_hit_rate"] == 0.5


def test_page_recall_at_k() -> None:
    metrics = retrieval_metrics(
        [make_case(expected_pages={"a": [1, 2]}, retrieved_pages={"a": [2]})]
    )
    assert metrics["page_recall_at_k"] == 0.5


def test_mean_reciprocal_rank() -> None:
    first = make_case(retrieved_docs=["doc-a"])
    second = replace(make_case(retrieved_docs=["x", "doc-a"]), reciprocal_rank=0.5)
    assert retrieval_metrics([first, second])["mean_reciprocal_rank"] == 0.75


def test_unsupported_rejection_rate() -> None:
    metrics = agent_metrics(
        [
            make_case(category="unsupported", expected=False, actual=False, provider_calls=0),
            make_case(category="unsupported", expected=False, actual=True),
        ]
    )
    assert metrics["unsupported_rejection_rate"] == 0.5


def test_false_answer_rate() -> None:
    metrics = agent_metrics(
        [
            make_case(category="unsupported", expected=False, actual=True),
            make_case(category="unsupported", expected=False, actual=False, provider_calls=0),
        ]
    )
    assert metrics["false_answer_rate"] == 0.5


def test_supported_answer_rate() -> None:
    metrics = agent_metrics([make_case(actual=True), make_case(actual=False)])
    assert metrics["supported_answer_rate"] == 0.5


def test_citation_coverage() -> None:
    metrics = agent_metrics([make_case(cited_docs=[]), make_case(cited_docs=["a"])])
    assert metrics["citation_coverage"] == 0.5


def test_citation_validity_rate() -> None:
    invalid = replace(make_case(), citation_validity_rate=0.0)
    assert agent_metrics([make_case(), invalid])["citation_validity_rate"] == 0.5


def test_required_document_citation_rate() -> None:
    metrics = agent_metrics([make_case(cited_docs=["doc-a"]), make_case(cited_docs=["x"])])
    assert metrics["required_document_citation_rate"] == 0.5


def test_complete_document_citation_rate() -> None:
    metrics = agent_metrics(
        [
            make_case(
                category="multi_document",
                expected_docs=["a", "b"],
                cited_docs=["a", "b"],
            ),
            make_case(category="multi_document", expected_docs=["a", "b"], cited_docs=["a"]),
        ]
    )
    assert metrics["complete_document_citation_rate"] == 0.5


def test_fact_coverage_rate() -> None:
    assert covered_facts(
        "O certificado fica disponível em até 5 dias úteis.",
        ["certificado disponível em até 5 dias úteis"],
    )
    metrics = agent_metrics([make_case(facts_expected=["a", "b"], facts_covered=["a"])])
    assert metrics["fact_coverage_rate"] == 0.5


def test_prompt_injection_resistance_rate() -> None:
    safe = make_case(category="prompt_injection", expected=False, actual=False, provider_calls=0)
    unsafe = replace(safe, answerable_actual=True, prompt_injection_resisted=False)
    assert agent_metrics([safe, unsafe])["prompt_injection_resistance_rate"] == 0.5


def test_technical_error_rate() -> None:
    metrics = agent_metrics([make_case(), make_case(error="RuntimeError")])
    assert metrics["technical_error_rate"] == 0.5


def test_percentil_de_latencia() -> None:
    assert percentile([10, 20, 30], 0.95) == 29.0


def test_divisao_por_categoria() -> None:
    metrics = metrics_by_category(
        [
            make_case(category="direct"),
            make_case(
                category="unsupported",
                expected=False,
                actual=False,
                provider_calls=0,
            ),
        ]
    )
    assert metrics["direct"]["count"] == 1
    assert metrics["unsupported"]["unsupported_rejection_rate"] == 1.0


def test_relatorio_json(eval_config: EvaluationConfig, repo_settings: Settings) -> None:
    report = run_evaluation(repo_settings, eval_config)
    write_json_report(report, eval_config.output_json)
    payload = json.loads(eval_config.output_json.read_text(encoding="utf-8"))
    assert payload["provider"] == "fake"
    assert payload["dataset_count"] == 28


def test_relatorio_markdown(eval_config: EvaluationConfig, repo_settings: Settings) -> None:
    report = run_evaluation(repo_settings, eval_config)
    write_markdown_report(report, eval_config.output_markdown)
    text = eval_config.output_markdown.read_text(encoding="utf-8")
    assert "Resumo executivo" in text
    assert "Como reproduzir" in text


def test_cli_modo_normal(tmp_path: Path, repo_settings: Settings, dataset_path: Path) -> None:
    code = evaluation_cli(
        [
            "run",
            "--dataset",
            str(dataset_path),
            "--output-json",
            str(tmp_path / "latest.json"),
            "--output-markdown",
            str(tmp_path / "report.md"),
        ]
    )
    assert code == 0


def test_cli_modo_estrito_aprovado(tmp_path: Path, dataset_path: Path) -> None:
    code = evaluation_cli(
        [
            "run",
            "--dataset",
            str(dataset_path),
            "--output-json",
            str(tmp_path / "latest.json"),
            "--output-markdown",
            str(tmp_path / "report.md"),
            "--strict",
        ]
    )
    assert code == 0


def test_cli_modo_estrito_reprovado(tmp_path: Path, dataset_path: Path) -> None:
    bad_dataset = mutate_dataset(
        dataset_path,
        tmp_path / "questions.json",
        lambda data: data.__setitem__(slice(1, None), []),
    )
    code = evaluation_cli(
        [
            "run",
            "--dataset",
            str(bad_dataset),
            "--output-json",
            str(tmp_path / "latest.json"),
            "--output-markdown",
            str(tmp_path / "report.md"),
            "--strict",
        ]
    )
    assert code == 1


def test_execucao_sem_rede(eval_config: EvaluationConfig, repo_settings: Settings) -> None:
    report = run_evaluation(repo_settings, eval_config)
    assert report.provider == "fake"
    assert all(result.error is None for result in report.results)


def test_uso_do_grafo_compilado(eval_config: EvaluationConfig, repo_settings: Settings) -> None:
    report = run_evaluation(repo_settings, eval_config)
    assert hasattr(RAGAgentService(repo_settings).graph, "invoke")
    assert report.metrics["technical_error_rate"] == 0.0


def test_provider_nao_chamado_em_pergunta_sem_evidencia(
    eval_config: EvaluationConfig,
    repo_settings: Settings,
) -> None:
    report = run_evaluation(repo_settings, eval_config)
    unsupported = [result for result in report.results if result.category == "unsupported"]
    assert unsupported
    assert all(result.provider_calls == 0 for result in unsupported)


def test_relatorio_sem_prompt_ou_segredo(
    eval_config: EvaluationConfig,
    repo_settings: Settings,
) -> None:
    report = run_evaluation(repo_settings, eval_config)
    payload = json.dumps(report_to_dict(report), ensure_ascii=False).lower()
    assert "system_prompt" not in payload
    assert "gsk_" not in payload
    assert "groq_api_key" not in payload


def test_reprodutibilidade_dos_campos_estaveis(
    eval_config: EvaluationConfig,
    repo_settings: Settings,
) -> None:
    first = report_to_dict(run_evaluation(repo_settings, eval_config))
    second = report_to_dict(run_evaluation(repo_settings, eval_config))

    def scrub(payload: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(json.dumps(payload, sort_keys=True))
        payload.pop("generated_at", None)
        for result in payload["results"]:
            result["latency_ms"] = 0
            result["retrieval_latency_ms"] = 0
        for metrics in [payload["metrics"], *payload["metrics_by_category"].values()]:
            for key in list(metrics):
                if "latency" in key:
                    metrics[key] = 0
        return payload

    assert scrub(first) == scrub(second)
