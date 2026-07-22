from __future__ import annotations

import logging
import time
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.agents.service import RAGAgentService, sanitize_request_id
from app.api.schemas import ChatRequest, ChatResponse, ErrorResponse, SourceResponse
from app.core.config import get_settings
from app.core.errors import (
    EduDocsError,
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from app.documents.manifest import enabled_documents, load_manifest
from app.ingestion.index import active_index_dir, validate_index

router = APIRouter()
LOGGER = logging.getLogger("edudocs.api.routes")


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


def get_chat_service() -> RAGAgentService:
    return RAGAgentService(get_settings())


def error_payload(detail: str, request_id: str, started: float) -> dict[str, object]:
    return {
        "detail": detail,
        "request_id": request_id,
        "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
    }


def log_error(
    request_id: str,
    status_code: int,
    started: float,
    provider: str,
    error_type: str,
) -> None:
    LOGGER.info(
        "chat_error",
        extra={
            "request_id": request_id,
            "route": "/api/chat",
            "status": status_code,
            "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
            "provider": provider,
            "evidence_count": 0,
            "answerable": False,
            "error_type": error_type,
        },
    )


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


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Entrada inválida."},
        429: {"model": ErrorResponse, "description": "Limite de taxa do provedor."},
        503: {"model": ErrorResponse, "description": "Provedor ou índice indisponível."},
        504: {"model": ErrorResponse, "description": "Timeout do provedor."},
    },
    summary="Responder pergunta com evidências documentais",
    description=(
        "Executa o agente RAG sobre os PDFs habilitados do corpus. A resposta usa somente "
        "evidências recuperadas e retorna fontes validadas por documento, versão e página."
    ),
)
async def chat(
    payload: ChatRequest,
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ChatResponse:
    started = time.perf_counter()
    request_id = sanitize_request_id(x_request_id)
    settings = get_settings()
    content_type = request.headers.get("content-type", "")
    if content_type and "application/json" not in content_type.lower():
        detail = "Content-Type deve ser application/json."
        raise HTTPException(status_code=400, detail=error_payload(detail, request_id, started))

    question = payload.question.strip()
    if not question:
        detail = "Pergunta não pode ser vazia."
        raise HTTPException(status_code=400, detail=error_payload(detail, request_id, started))
    if len(question) > settings.max_question_length:
        detail = "Pergunta acima do limite configurado."
        raise HTTPException(status_code=400, detail=error_payload(detail, request_id, started))

    try:
        service = get_chat_service()
        result = await service.answer(question=question, request_id=request_id)
    except LLMProviderRateLimitError as exc:
        log_error(request_id, 429, started, settings.llm_provider, exc.__class__.__name__)
        raise HTTPException(
            status_code=429,
            detail=error_payload("Provedor retornou limite de taxa.", request_id, started),
        ) from exc
    except LLMProviderTimeoutError as exc:
        log_error(request_id, 504, started, settings.llm_provider, exc.__class__.__name__)
        raise HTTPException(
            status_code=504,
            detail=error_payload("Timeout ao gerar resposta.", request_id, started),
        ) from exc
    except (LLMProviderUnavailableError, EduDocsError) as exc:
        log_error(request_id, 503, started, settings.llm_provider, exc.__class__.__name__)
        raise HTTPException(
            status_code=503,
            detail=error_payload("Serviço indisponível para gerar resposta.", request_id, started),
        ) from exc

    return ChatResponse(
        answer=result.answer,
        answerable=result.answerable,
        sources=[SourceResponse.model_validate(source) for source in result.sources],
        request_id=result.request_id,
        latency_ms=result.latency_ms,
    )
