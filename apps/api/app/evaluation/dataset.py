from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz

from app.core.config import Settings
from app.documents.manifest import enabled_documents, load_manifest
from app.evaluation.models import SUPPORTED_CATEGORIES, EvaluationCase


class EvaluationDatasetError(ValueError):
    """Erro de validação do dataset de avaliação."""


def load_evaluation_cases(path: Path, settings: Settings) -> list[EvaluationCase]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationDatasetError(f"Dataset não encontrado: {path}") from exc
    except UnicodeDecodeError as exc:
        raise EvaluationDatasetError("Dataset deve estar em UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationDatasetError(f"Dataset JSON inválido: {exc}") from exc

    if not isinstance(raw, list):
        raise EvaluationDatasetError("Dataset deve ser uma lista de casos.")

    manifest = load_manifest(settings.resolved_manifest_path, settings.repo_root)
    documents = {document.id: document for document in enabled_documents(manifest)}
    page_counts = {
        document.id: _pdf_page_count(settings.repo_root / document.pdf_path)
        for document in documents.values()
    }

    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise EvaluationDatasetError(f"Caso #{index} deve ser um objeto JSON.")
        case = _parse_case(item, index)
        if case.id in seen_ids:
            raise EvaluationDatasetError(f"ID duplicado no dataset: {case.id}")
        seen_ids.add(case.id)
        _validate_case(case, documents, page_counts)
        cases.append(case)

    return cases


def _parse_case(item: dict[str, Any], index: int) -> EvaluationCase:
    required = {
        "id",
        "question",
        "answerable",
        "expected_documents",
        "expected_pages",
        "expected_facts",
        "category",
    }
    missing = sorted(required - set(item))
    if missing:
        raise EvaluationDatasetError(f"Caso #{index} sem campos obrigatórios: {missing}")

    if not isinstance(item["id"], str) or not item["id"].strip():
        raise EvaluationDatasetError(f"Caso #{index} possui ID inválido.")
    if not isinstance(item["question"], str) or not item["question"].strip():
        raise EvaluationDatasetError(f"Caso {item['id']} possui pergunta inválida.")
    if not isinstance(item["answerable"], bool):
        raise EvaluationDatasetError(f"Caso {item['id']} possui answerable inválido.")
    if not isinstance(item["category"], str) or not item["category"].strip():
        raise EvaluationDatasetError(f"Caso {item['id']} possui categoria inválida.")

    expected_documents = item["expected_documents"]
    if not isinstance(expected_documents, list) or not all(
        isinstance(value, str) and value.strip() for value in expected_documents
    ):
        raise EvaluationDatasetError(f"Caso {item['id']} possui documentos esperados inválidos.")

    expected_pages = item["expected_pages"]
    if not isinstance(expected_pages, dict):
        raise EvaluationDatasetError(f"Caso {item['id']} possui páginas esperadas inválidas.")
    parsed_pages: dict[str, list[int]] = {}
    for document_id, pages in expected_pages.items():
        if not isinstance(document_id, str) or not isinstance(pages, list):
            raise EvaluationDatasetError(f"Caso {item['id']} possui páginas esperadas inválidas.")
        if not pages or not all(isinstance(page, int) and page > 0 for page in pages):
            raise EvaluationDatasetError(f"Caso {item['id']} possui página esperada inválida.")
        parsed_pages[document_id] = sorted(set(pages))

    expected_facts = item["expected_facts"]
    if not isinstance(expected_facts, list) or not all(
        isinstance(value, str) and value.strip() for value in expected_facts
    ):
        raise EvaluationDatasetError(f"Caso {item['id']} possui fatos esperados inválidos.")

    return EvaluationCase(
        id=item["id"].strip(),
        question=item["question"].strip(),
        category=item["category"].strip(),
        answerable=item["answerable"],
        expected_documents=[value.strip() for value in expected_documents],
        expected_pages=parsed_pages,
        expected_facts=[value.strip() for value in expected_facts],
    )


def _validate_case(
    case: EvaluationCase,
    documents: dict[str, object],
    page_counts: dict[str, int],
) -> None:
    if case.category not in SUPPORTED_CATEGORIES:
        raise EvaluationDatasetError(f"Categoria inválida em {case.id}: {case.category}")

    unknown_docs = sorted(set(case.expected_documents) - set(documents))
    if unknown_docs:
        raise EvaluationDatasetError(
            f"Documento esperado inexistente em {case.id}: {', '.join(unknown_docs)}"
        )

    pages_without_doc = sorted(set(case.expected_pages) - set(case.expected_documents))
    if pages_without_doc:
        raise EvaluationDatasetError(
            f"Páginas esperadas sem documento correspondente em {case.id}: "
            f"{', '.join(pages_without_doc)}"
        )

    for document_id, pages in case.expected_pages.items():
        max_page = page_counts[document_id]
        invalid_pages = [page for page in pages if page > max_page]
        if invalid_pages:
            raise EvaluationDatasetError(
                f"Página esperada inexistente em {case.id}: {document_id} {invalid_pages}"
            )

    if case.category in {"direct", "multi_document"} and not case.answerable:
        raise EvaluationDatasetError(
            f"Caso {case.id} é respondível pela categoria, mas answerable=false."
        )
    if case.category == "unsupported" and case.answerable:
        raise EvaluationDatasetError(f"Caso {case.id} unsupported não pode ser answerable=true.")
    if case.category == "unsupported" and (case.expected_documents or case.expected_pages):
        raise EvaluationDatasetError(f"Caso {case.id} unsupported não deve esperar documentos.")
    if case.category == "prompt_injection" and case.answerable:
        raise EvaluationDatasetError(
            f"Caso {case.id} prompt_injection deve esperar recusa ou resistência."
        )
    if case.answerable and not case.expected_documents:
        raise EvaluationDatasetError(
            f"Caso respondível {case.id} deve possuir documentos esperados."
        )
    if case.answerable and not case.expected_pages:
        raise EvaluationDatasetError(f"Caso respondível {case.id} deve possuir páginas esperadas.")
    if case.category == "multi_document" and len(set(case.expected_documents)) < 2:
        raise EvaluationDatasetError(
            f"Caso multidocumento {case.id} deve esperar ao menos 2 documentos."
        )


def _pdf_page_count(path: Path) -> int:
    with fitz.open(path) as pdf:
        return int(pdf.page_count)
