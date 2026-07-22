from __future__ import annotations


class EduDocsError(Exception):
    """Erro base da aplicação."""


class ManifestError(EduDocsError):
    """Erro de manifesto do corpus."""


class DocumentExtractionError(EduDocsError):
    """Erro de extração de documento."""


class IngestionError(EduDocsError):
    """Erro do pipeline de ingestão."""


class EmbeddingError(EduDocsError):
    """Erro do provedor de embeddings."""


class IndexError(EduDocsError):
    """Erro de índice local."""
