from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        examples=["Como solicito meu certificado?"],
        description="Pergunta em português do Brasil sobre os documentos disponíveis.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"question": "Como solicito meu certificado?"}],
        }
    }


class SourceResponse(BaseModel):
    document_id: str
    title: str
    version: str
    page: int
    section: str | None
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    answerable: bool
    sources: list[SourceResponse]
    request_id: str
    latency_ms: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "Para receber o certificado, cumpra os requisitos do curso.",
                    "answerable": True,
                    "sources": [
                        {
                            "document_id": "guia-de-certificados",
                            "title": "Guia de Certificados",
                            "version": "1.0",
                            "page": 3,
                            "section": "6. Prazo de emissão",
                            "excerpt": "Após o cumprimento de todos os requisitos...",
                        }
                    ],
                    "request_id": "exemplo-local-1",
                    "latency_ms": 42,
                },
                {
                    "answer": (
                        "Não encontrei informações suficientes nos documentos disponíveis "
                        "para responder com segurança."
                    ),
                    "answerable": False,
                    "sources": [],
                    "request_id": "exemplo-local-2",
                    "latency_ms": 18,
                },
            ],
        }
    }


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
    latency_ms: int | None = None
