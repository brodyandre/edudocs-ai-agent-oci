from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.evaluation.models import EvaluationReport


def report_to_dict(report: EvaluationReport) -> dict[str, Any]:
    return {
        "format_version": report.format_version,
        "generated_at": report.generated_at,
        "corpus_fingerprint": report.corpus_fingerprint,
        "index_fingerprint": report.index_fingerprint,
        "dataset_path": report.dataset_path,
        "dataset_count": report.dataset_count,
        "top_k": report.top_k,
        "provider": report.provider,
        "thresholds": report.thresholds,
        "metrics": report.metrics,
        "metrics_by_category": report.metrics_by_category,
        "criteria_passed": report.criteria_passed,
        "criteria_failed": report.criteria_failed,
        "errors": report.errors,
        "results": [asdict(result) for result in report.results],
    }


def write_json_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report_to_dict(report)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    failed_cases = [result for result in report.results if not result.passed]
    lines = [
        "# Relatório de Avaliação RAG",
        "",
        "## 1. Resumo executivo",
        (
            f"A avaliação determinística executou {report.dataset_count} casos com provider "
            f"`{report.provider}` e top-k `{report.top_k}`. "
            f"{len(report.criteria_passed)} critérios foram aprovados e "
            f"{len(report.criteria_failed)} critérios foram reprovados."
        ),
        "",
        "## 2. Data da execução",
        report.generated_at,
        "",
        "## 3. Fingerprint do corpus",
        f"`{report.corpus_fingerprint}`",
        "",
        "## 4. Fingerprint do índice",
        f"`{report.index_fingerprint}`",
        "",
        "## 5. Configuração",
        f"- Dataset: `{report.dataset_path}`",
        f"- Top-k: `{report.top_k}`",
        f"- Provider: `{report.provider}`",
        "- Chamadas externas: não usadas na avaliação padrão.",
        "",
        "## 6. Quantidade de casos",
        f"Total: {report.dataset_count}",
        "",
        "## 7. Métricas globais",
        _metrics_table(report.metrics),
        "",
        "## 8. Tabela por categoria",
        _category_table(report.metrics_by_category),
        "",
        "## 9. Critérios aprovados",
        _criteria_table(report.criteria_passed) if report.criteria_passed else "Nenhum.",
        "",
        "## 10. Critérios reprovados",
        _criteria_table(report.criteria_failed) if report.criteria_failed else "Nenhum.",
        "",
        "## 11. Casos com falha",
        _failed_cases_table(failed_cases),
        "",
        "## 12. Análise dos principais problemas",
        _failure_analysis(report, failed_cases),
        "",
        "## 13. Limitações",
        (
            "A validação factual é determinística e baseada em frase normalizada ou termos "
            "essenciais; ela não substitui julgamento semântico humano. Latência local varia "
            "por máquina e não deve ser tratada como promessa de desempenho."
        ),
        "",
        "## 14. Próximos ajustes recomendados",
        (
            "Investigar casos com baixa cobertura factual, revisar recuperação por páginas "
            "quando necessário e manter critérios fixos entre execuções comparáveis."
        ),
        "",
        "## 15. Como reproduzir",
        "```bash",
        "cd apps/api",
        "../../.venv/bin/python -m app.evaluation.cli run",
        "../../.venv/bin/python -m app.evaluation.cli run --strict",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _metrics_table(metrics: dict[str, Any]) -> str:
    rows = ["| Métrica | Valor |", "|---|---:|"]
    rows.extend(f"| `{name}` | {_format_value(value)} |" for name, value in sorted(metrics.items()))
    return "\n".join(rows)


def _category_table(metrics_by_category: dict[str, dict[str, Any]]) -> str:
    rows = [
        "| Categoria | Casos | Retrieval hit | Answerable accuracy | Latência média ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for category, metrics in metrics_by_category.items():
        rows.append(
            "| "
            f"{category} | {metrics.get('count')} | "
            f"{_format_value(metrics.get('retrieval_hit_rate'))} | "
            f"{_format_value(metrics.get('answerable_accuracy'))} | "
            f"{_format_value(metrics.get('latency_mean_ms'))} |"
        )
    return "\n".join(rows)


def _criteria_table(criteria: dict[str, float]) -> str:
    rows = ["| Critério | Valor |", "|---|---:|"]
    rows.extend(
        f"| `{name}` | {_format_value(value)} |" for name, value in sorted(criteria.items())
    )
    return "\n".join(rows)


def _failed_cases_table(failed_cases) -> str:
    if not failed_cases:
        return "Nenhum caso reprovado."
    rows = ["| ID | Categoria | Erro |", "|---|---|---|"]
    for result in failed_cases:
        reason = result.error or "métrica comportamental abaixo do esperado"
        rows.append(f"| `{result.id}` | {result.category} | {reason} |")
    return "\n".join(rows)


def _failure_analysis(report: EvaluationReport, failed_cases) -> str:
    observations: list[str] = []
    fact_coverage = report.metrics.get("fact_coverage_rate")
    if fact_coverage is not None and fact_coverage < 1:
        observations.append(
            f"`fact_coverage_rate` ficou em {_format_value(fact_coverage)}; "
            "o provider falso resume evidências e nem sempre reproduz os fatos esperados."
        )
    complete_citations = report.metrics.get("complete_document_citation_rate")
    if complete_citations is not None and complete_citations < 1:
        observations.append(
            f"`complete_document_citation_rate` ficou em {_format_value(complete_citations)}; "
            "algumas respostas multidocumento citam apenas parte dos documentos esperados."
        )
    page_recall = report.metrics.get("page_recall_at_k")
    if page_recall is not None and page_recall < 1:
        observations.append(
            f"`page_recall_at_k` ficou em {_format_value(page_recall)}; a recuperação nem sempre "
            "traz todas as páginas esperadas no top-k."
        )

    if not failed_cases:
        if observations:
            return "\n".join(f"- {item}" for item in observations)
        return "Não houve falhas por caso nesta execução."

    categories = sorted({result.category for result in failed_cases})
    intro = (
        "As falhas por caso se concentram nas categorias "
        + ", ".join(f"`{category}`" for category in categories)
        + "."
    )
    if observations:
        return intro + "\n" + "\n".join(f"- {item}" for item in observations)
    return (
        intro
        + " Verifique recuperação, suficiência, citação e cobertura factual antes de alterar dados."
    )
