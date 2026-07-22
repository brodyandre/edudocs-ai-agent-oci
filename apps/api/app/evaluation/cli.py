from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import Settings
from app.evaluation.dataset import EvaluationDatasetError
from app.evaluation.models import DEFAULT_THRESHOLDS, EvaluationConfig
from app.evaluation.report import write_json_report, write_markdown_report
from app.evaluation.runner import run_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa avaliação determinística do RAG.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Executa a avaliação e gera relatórios.")
    run.add_argument("--dataset", type=Path, default=None)
    run.add_argument("--output-json", type=Path, default=None)
    run.add_argument("--output-markdown", type=Path, default=None)
    run.add_argument("--top-k", type=int, default=None)
    run.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings(llm_provider="fake", embedding_provider="fake")
    config = EvaluationConfig(
        dataset_path=_repo_path(settings, args.dataset or Path("corpus/evaluation/questions.json")),
        output_json=_repo_path(
            settings,
            args.output_json or Path("corpus/evaluation/results/latest.json"),
        ),
        output_markdown=_repo_path(
            settings,
            args.output_markdown or Path("docs/evaluation-report.md"),
        ),
        top_k=args.top_k or settings.chat_top_k,
        strict=args.strict,
        thresholds=dict(DEFAULT_THRESHOLDS),
    )

    try:
        report = run_evaluation(settings, config)
        write_json_report(report, config.output_json)
        write_markdown_report(report, config.output_markdown)
    except (EvaluationDatasetError, ValueError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    print(f"Relatório JSON: {config.output_json}")
    print(f"Relatório Markdown: {config.output_markdown}")
    if report.criteria_failed:
        print("Critérios reprovados: " + ", ".join(sorted(report.criteria_failed)))
    else:
        print("Todos os critérios obrigatórios foram aprovados.")
    if config.strict and report.criteria_failed:
        return 1
    return 0


def _repo_path(settings: Settings, path: Path) -> Path:
    return path if path.is_absolute() else settings.repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
