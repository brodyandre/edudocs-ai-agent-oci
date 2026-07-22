from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

from app.core.errors import EmbeddingError

FloatMatrix = NDArray[np.float32]


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed_texts(self, texts: list[str], batch_size: int) -> FloatMatrix:
        raise NotImplementedError


def l2_normalize(matrix: FloatMatrix) -> FloatMatrix:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 32) -> None:
        if dimension < 2:
            raise EmbeddingError("Dimensão do embedding falso deve ser maior que 1.")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str], batch_size: int) -> FloatMatrix:
        del batch_size
        rows: list[list[float]] = []
        for text in texts:
            vector = np.zeros(self.dimension, dtype=np.float32)
            tokens = [token for token in text.lower().split() if token]
            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                vector[index] += 1.0
            rows.append(vector.tolist())
        return l2_normalize(np.array(rows, dtype=np.float32))


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Provider real com carregamento preguiçoso para evitar download na importação."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: object | None = None
        self._dimension: int | None = None

    def _load_model(self) -> object:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingError(
                    "sentence-transformers não está instalado. Instale o extra de embeddings "
                    "somente no ambiente que for construir índice real."
                ) from exc
            self._model = SentenceTransformer(self.model_name)
            self._dimension = int(self._model.get_sentence_embedding_dimension())
        return self._model

    @property
    def dimension(self) -> int:
        self._load_model()
        if self._dimension is None:
            raise EmbeddingError("Não foi possível obter a dimensão do modelo de embeddings.")
        return self._dimension

    def embed_texts(self, texts: list[str], batch_size: int) -> FloatMatrix:
        model = self._load_model()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        matrix = np.asarray(embeddings, dtype=np.float32)
        if matrix.ndim != 2:
            raise EmbeddingError("Modelo retornou embeddings em formato inválido.")
        return l2_normalize(matrix)
