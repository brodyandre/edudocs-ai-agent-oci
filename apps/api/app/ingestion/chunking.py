from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from app.documents.pdf import PageText

SECTION_PATTERN = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+.+|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.!?]{3,80})$")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    document_title: str
    document_version: str
    page_start: int
    page_end: int
    section: str | None
    text: str
    ordinal: int
    content_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_chunk_id(document_id: str, ordinal: int, digest: str) -> str:
    return f"{document_id}:{ordinal:04d}:{digest[:12]}"


def detect_section(line: str, current_section: str | None) -> str | None:
    stripped = line.strip()
    if SECTION_PATTERN.match(stripped) and len(stripped.split()) <= 10:
        return stripped
    return current_section


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                piece = paragraph[start : start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
                if start + chunk_size >= len(paragraph):
                    break
                start += max(1, chunk_size - chunk_overlap)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current.strip())
        if chunk_overlap > 0 and chunks:
            overlap_text = chunks[-1][-chunk_overlap:].strip()
            current = f"{overlap_text}\n\n{paragraph}".strip()
        else:
            current = paragraph

    if current.strip():
        chunks.append(current.strip())

    return chunks


def chunk_pages(pages: list[PageText], chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    ordinal = 0

    for page in pages:
        section: str | None = None
        for line in page.text.splitlines():
            section = detect_section(line, section)

        for chunk_text in split_text(page.text, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            stripped = chunk_text.strip()
            if not stripped:
                continue
            digest = content_hash(stripped)
            chunks.append(
                Chunk(
                    chunk_id=stable_chunk_id(page.document_id, ordinal, digest),
                    document_id=page.document_id,
                    document_title=page.document_title,
                    document_version=page.document_version,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    section=section,
                    text=stripped,
                    ordinal=ordinal,
                    content_hash=digest,
                )
            )
            ordinal += 1

    return chunks
