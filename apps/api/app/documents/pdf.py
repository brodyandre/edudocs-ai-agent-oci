from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.errors import DocumentExtractionError
from app.documents.manifest import ManifestDocument


@dataclass(frozen=True)
class PageText:
    document_id: str
    document_title: str
    document_version: str
    page_number: int
    text: str


def extract_pdf_pages(document: ManifestDocument, repo_root: Path) -> list[PageText]:
    pdf_path = (repo_root / document.pdf_path).resolve()
    if not pdf_path.is_file():
        raise DocumentExtractionError(f"PDF não encontrado: {document.pdf_path}")
    if pdf_path.stat().st_size == 0:
        raise DocumentExtractionError(f"PDF vazio: {document.pdf_path}")

    try:
        pdf = fitz.open(pdf_path)
    except Exception as exc:
        raise DocumentExtractionError(f"PDF corrompido ou inválido: {document.pdf_path}") from exc

    try:
        if pdf.page_count == 0:
            raise DocumentExtractionError(f"PDF sem páginas: {document.pdf_path}")

        pages: list[PageText] = []
        for index in range(pdf.page_count):
            text = pdf.load_page(index).get_text("text")
            if not text.strip():
                raise DocumentExtractionError(
                    f"Página sem texto extraível: {document.pdf_path} página {index + 1}"
                )
            pages.append(
                PageText(
                    document_id=document.id,
                    document_title=document.title,
                    document_version=document.version,
                    page_number=index + 1,
                    text=text,
                )
            )
        return pages
    finally:
        pdf.close()
