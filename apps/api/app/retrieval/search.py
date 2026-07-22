from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import Settings
from app.core.errors import IndexError
from app.ingestion.embeddings import EmbeddingProvider
from app.ingestion.index import active_index_dir, read_json, validate_index


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    score: float
    semantic_score: float
    lexical_score: float
    metadata: dict[str, object]
    text: str


class LocalIndex:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.embeddings: np.ndarray | None = None
        self.metadata: list[dict[str, object]] | None = None
        self.vectorizer: object | None = None
        self.lexical_matrix: object | None = None

    @classmethod
    def load(cls, settings: Settings) -> LocalIndex:
        index_path = active_index_dir(settings.resolved_index_dir)
        validate_index(index_path, settings=settings)
        instance = cls(index_path)
        instance.embeddings = np.load(index_path / "embeddings.npz")["embeddings"]
        instance.metadata = read_json(index_path / "metadata.json")
        try:
            with (index_path / "lexical.pkl").open("rb") as file:
                lexical = pickle.load(file)
        except Exception as exc:
            raise IndexError("Índice lexical corrompido.") from exc
        instance.vectorizer = lexical["vectorizer"]
        instance.lexical_matrix = lexical["matrix"]
        return instance

    def search(
        self,
        query: str,
        provider: EmbeddingProvider,
        top_k: int,
        batch_size: int,
    ) -> list[SearchResult]:
        if self.embeddings is None or self.metadata is None:
            raise IndexError("Índice não carregado.")
        if self.vectorizer is None or self.lexical_matrix is None:
            raise IndexError("Índice lexical não carregado.")

        query_embedding = provider.embed_texts([query], batch_size=batch_size)[0]
        semantic_scores = self.embeddings @ query_embedding

        query_vector = self.vectorizer.transform([query])
        lexical_scores = np.asarray((self.lexical_matrix @ query_vector.T).todense()).ravel()
        if lexical_scores.max(initial=0.0) > 0:
            lexical_scores = lexical_scores / lexical_scores.max()

        combined = (0.7 * semantic_scores) + (0.3 * lexical_scores)
        indices = np.argsort(combined)[::-1][:top_k]

        results: list[SearchResult] = []
        for index in indices:
            item = self.metadata[int(index)]
            results.append(
                SearchResult(
                    chunk_id=str(item["chunk_id"]),
                    score=float(combined[index]),
                    semantic_score=float(semantic_scores[index]),
                    lexical_score=float(lexical_scores[index]),
                    metadata={key: value for key, value in item.items() if key != "text"},
                    text=str(item["text"]),
                )
            )
        return results
