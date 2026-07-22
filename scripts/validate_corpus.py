#!/usr/bin/env python3
"""Valida o corpus fictício da EduDocs Academy."""

from __future__ import annotations

import hashlib
import os
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import fitz


MANIFEST_PATH = ROOT / "corpus" / "manifest.json"
QUESTIONS_PATH = ROOT / "corpus" / "evaluation" / "questions.json"

EXPECTED_DOC_IDS = {
    "regulamento-do-estudante",
    "politica-de-cancelamento-e-reembolso",
    "guia-de-certificados",
    "faq-de-cursos-e-matriculas",
    "politica-de-privacidade",
}

MIN_QUESTIONS_BY_CATEGORY = {
    "direct": 15,
    "multi_document": 5,
    "unsupported": 5,
    "prompt_injection": 3,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_markdown(path: Path, expected_title: str, problems: list[str]) -> None:
    if not path.is_file():
        problems.append(f"Markdown ausente: {path.relative_to(ROOT)}")
        return

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        problems.append(f"Markdown não está em UTF-8: {path.relative_to(ROOT)}")
        return

    if "\ufffd" in text:
        problems.append(f"Markdown contém caractere de substituição: {path.relative_to(ROOT)}")
    if f"# {expected_title}" not in text:
        problems.append(f"Título não encontrado no Markdown: {path.relative_to(ROOT)}")
    for marker in ["**Identificador:**", "**Versão:**", "**Data de vigência:**", "## Sumário"]:
        if marker not in text:
            problems.append(f"Metadado obrigatório ausente em {path.relative_to(ROOT)}: {marker}")


def validate_pdf(path: Path, title: str, expected_hash: str, problems: list[str]) -> int:
    if not path.is_file():
        problems.append(f"PDF ausente: {path.relative_to(ROOT)}")
        return 0
    if path.stat().st_size == 0:
        problems.append(f"PDF vazio: {path.relative_to(ROOT)}")
        return 0

    if sha256(path) != expected_hash:
        problems.append(f"Hash divergente no manifesto: {path.relative_to(ROOT)}")

    try:
        document = fitz.open(path)
    except Exception as exc:
        problems.append(f"PDF inválido: {path.relative_to(ROOT)} ({exc})")
        return 0

    try:
        page_count = document.page_count
        if page_count == 0:
            problems.append(f"PDF sem páginas: {path.relative_to(ROOT)}")
            return 0

        full_text = []
        for page_index in range(page_count):
            text = document.load_page(page_index).get_text("text").strip()
            if not text:
                problems.append(f"Página sem texto extraível: {path.relative_to(ROOT)} página {page_index + 1}")
            if "\ufffd" in text:
                problems.append(f"PDF contém caractere de substituição: {path.relative_to(ROOT)} página {page_index + 1}")
            full_text.append(text)

        if title not in "\n".join(full_text[:2]):
            problems.append(f"Título não identificável no PDF: {path.relative_to(ROOT)}")
        return page_count
    finally:
        document.close()


def validate_questions(existing_ids: set[str], page_counts: dict[str, int], problems: list[str]) -> Counter:
    if not QUESTIONS_PATH.is_file():
        problems.append("Dataset de avaliação ausente: corpus/evaluation/questions.json")
        return Counter()

    questions = load_json(QUESTIONS_PATH)
    if not isinstance(questions, list):
        problems.append("questions.json deve conter uma lista de perguntas.")
        return Counter()

    seen_ids: set[str] = set()
    categories: Counter = Counter()
    required_keys = {
        "id",
        "question",
        "answerable",
        "expected_documents",
        "expected_pages",
        "expected_facts",
        "category",
    }

    for item in questions:
        if not isinstance(item, dict):
            problems.append("Cada pergunta deve ser um objeto JSON.")
            continue

        missing = required_keys - set(item)
        if missing:
            problems.append(f"Pergunta com campos ausentes: {sorted(missing)}")
            continue

        question_id = str(item["id"])
        if question_id in seen_ids:
            problems.append(f"ID de pergunta duplicado: {question_id}")
        seen_ids.add(question_id)

        category = str(item["category"])
        categories[category] += 1

        expected_documents = item["expected_documents"]
        if not isinstance(expected_documents, list):
            problems.append(f"expected_documents deve ser lista em {question_id}")
            continue

        for doc_id in expected_documents:
            if doc_id not in existing_ids:
                problems.append(f"Pergunta {question_id} aponta para documento inexistente: {doc_id}")

        expected_pages = item["expected_pages"]
        if not isinstance(expected_pages, dict):
            problems.append(f"expected_pages deve ser objeto em {question_id}")
            continue

        for doc_id, pages in expected_pages.items():
            if doc_id not in existing_ids:
                problems.append(f"Pergunta {question_id} aponta páginas de documento inexistente: {doc_id}")
                continue
            if not isinstance(pages, list):
                problems.append(f"Páginas esperadas devem ser lista em {question_id}/{doc_id}")
                continue
            for page in pages:
                if not isinstance(page, int) or page < 1 or page > page_counts.get(doc_id, 0):
                    problems.append(f"Página esperada fora do limite em {question_id}/{doc_id}: {page}")

    for category, minimum in MIN_QUESTIONS_BY_CATEGORY.items():
        if categories[category] < minimum:
            problems.append(f"Categoria {category} tem {categories[category]} perguntas; mínimo é {minimum}.")

    return categories


def main() -> int:
    problems: list[str] = []
    if not MANIFEST_PATH.is_file():
        print("ERRO: corpus/manifest.json ausente.")
        return 1

    manifest = load_json(MANIFEST_PATH)
    documents = manifest.get("documents") if isinstance(manifest, dict) else None
    if not isinstance(documents, list):
        print("ERRO: manifesto inválido; campo documents deve ser uma lista.")
        return 1

    ids = [doc.get("id") for doc in documents if isinstance(doc, dict)]
    if len(ids) != len(set(ids)):
        problems.append("IDs duplicados no manifesto.")

    existing_ids = set(ids)
    missing_ids = EXPECTED_DOC_IDS - existing_ids
    extra_ids = existing_ids - EXPECTED_DOC_IDS
    if missing_ids:
        problems.append(f"Documentos obrigatórios ausentes no manifesto: {sorted(missing_ids)}")
    if extra_ids:
        problems.append(f"Documentos inesperados no manifesto: {sorted(extra_ids)}")

    page_counts: dict[str, int] = {}
    for doc in documents:
        if not isinstance(doc, dict):
            problems.append("Entrada inválida no manifesto.")
            continue
        doc_id = doc.get("id")
        title = doc.get("title")
        source_path = ROOT / str(doc.get("source_path", ""))
        pdf_path = ROOT / str(doc.get("pdf_path", ""))
        expected_hash = str(doc.get("sha256", ""))

        if not doc.get("enabled"):
            problems.append(f"Documento não habilitado: {doc_id}")
        if doc_id not in EXPECTED_DOC_IDS:
            problems.append(f"ID não esperado no manifesto: {doc_id}")
        if not source_path.resolve().is_relative_to(ROOT):
            problems.append(f"Caminho de fonte fora do repositório: {source_path}")
            continue
        if not pdf_path.resolve().is_relative_to(ROOT):
            problems.append(f"Caminho de PDF fora do repositório: {pdf_path}")
            continue

        validate_markdown(source_path, str(title), problems)
        page_counts[str(doc_id)] = validate_pdf(pdf_path, str(title), expected_hash, problems)

    categories = validate_questions(existing_ids, page_counts, problems)

    if problems:
        print("ERRO: problemas encontrados no corpus:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("OK: corpus validado com sucesso.")
    print("Páginas por documento:")
    for doc_id in sorted(page_counts):
        print(f"- {doc_id}: {page_counts[doc_id]}")
    print("Perguntas por categoria:")
    for category in sorted(categories):
        print(f"- {category}: {categories[category]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
