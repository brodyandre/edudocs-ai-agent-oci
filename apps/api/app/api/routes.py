from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import EduDocsError
from app.documents.manifest import enabled_documents, load_manifest
from app.ingestion.index import active_index_dir, validate_index

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    index_format_version: str
    chunks: int


class DocumentResponse(BaseModel):
    id: str
    title: str
    version: str
    effective_date: str
    category: str
    language: str


class DocumentsResponse(BaseModel):
    documents: list[DocumentResponse]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="edudocs-ai-api")


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    settings = get_settings()
    try:
        index_manifest = validate_index(
            active_index_dir(settings.resolved_index_dir),
            settings=settings,
        )
    except EduDocsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Índice local não está pronto.",
        ) from exc
    return ReadyResponse(
        status="ready",
        index_format_version=str(index_manifest["format_version"]),
        chunks=int(index_manifest["chunks"]),
    )


@router.get("/api/documents", response_model=DocumentsResponse)
async def list_documents() -> DocumentsResponse:
    settings = get_settings()
    try:
        manifest = load_manifest(settings.resolved_manifest_path, settings.repo_root)
    except EduDocsError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível carregar o manifesto.",
        ) from exc

    return DocumentsResponse(
        documents=[
            DocumentResponse(
                id=document.id,
                title=document.title,
                version=document.version,
                effective_date=document.effective_date,
                category=document.category,
                language=document.language,
            )
            for document in enabled_documents(manifest)
        ]
    )
