from __future__ import annotations

from app.documents.manifest import CorpusManifest, enabled_documents
from app.providers.base import EvidencePayload, LLMResult


def excerpt_for(text: str, max_length: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "…"


def validate_sources(
    provider_result: LLMResult | None,
    evidences: list[EvidencePayload],
    manifest: CorpusManifest,
) -> list[dict[str, object]]:
    if provider_result is None:
        return []

    enabled = {document.id: document for document in enabled_documents(manifest)}
    evidence_by_chunk = {evidence.chunk_id: evidence for evidence in evidences}
    used_ids = provider_result.used_chunk_ids or [evidence.chunk_id for evidence in evidences[:2]]

    sources: list[dict[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for chunk_id in used_ids:
        evidence = evidence_by_chunk.get(chunk_id)
        if evidence is None:
            continue
        document = enabled.get(evidence.document_id)
        if document is None or document.version != evidence.document_version:
            continue
        if evidence.page_start < 1 or evidence.page_end < evidence.page_start:
            continue
        excerpt = excerpt_for(evidence.text)
        if excerpt.replace("…", "")[:40] not in " ".join(evidence.text.split()):
            continue
        key = (evidence.document_id, evidence.page_start, excerpt[:40])
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "document_id": evidence.document_id,
                "title": evidence.document_title,
                "version": evidence.document_version,
                "page": evidence.page_start,
                "section": evidence.section,
                "excerpt": excerpt,
            }
        )
    return sources
