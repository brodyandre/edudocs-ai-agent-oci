from __future__ import annotations

from app.core.config import Settings
from app.core.errors import EmbeddingError
from app.ingestion.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower().strip()
    if provider == "fake":
        return FakeEmbeddingProvider(dimension=settings.fake_embedding_dimension)
    if provider in {"sentence-transformers", "sentence_transformers"}:
        return SentenceTransformerEmbeddingProvider(model_name=settings.embedding_model)
    raise EmbeddingError(f"Provedor de embeddings desconhecido: {settings.embedding_provider}")
