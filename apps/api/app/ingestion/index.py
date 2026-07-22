from __future__ import annotations

import json
import pickle
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.core.config import Settings
from app.core.errors import IndexError, IngestionError
from app.documents.manifest import (
    CorpusManifest,
    corpus_fingerprint,
    enabled_documents,
    load_manifest,
)
from app.documents.pdf import extract_pdf_pages
from app.ingestion.chunking import Chunk, chunk_pages
from app.ingestion.embeddings import EmbeddingProvider
from app.ingestion.normalization import normalize_pages

INDEX_FORMAT_VERSION = "1"


@dataclass(frozen=True)
class BuildSummary:
    documents: int
    pages: int
    chunks: int
    embedding_dimension: int
    index_path: Path
    size_bytes: int


def active_index_dir(index_dir: Path) -> Path:
    return index_dir / "active"


def index_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_chunks(settings: Settings) -> tuple[CorpusManifest, list[Chunk], int]:
    manifest = load_manifest(settings.resolved_manifest_path, settings.repo_root)
    chunks: list[Chunk] = []
    page_count = 0

    for document in enabled_documents(manifest):
        pages = normalize_pages(extract_pdf_pages(document, settings.repo_root))
        page_count += len(pages)
        chunks.extend(
            chunk_pages(
                pages,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
        )

    if not chunks:
        raise IngestionError("Nenhum chunk foi produzido a partir do corpus.")

    return manifest, chunks, page_count


def build_index(settings: Settings, embedding_provider: EmbeddingProvider) -> BuildSummary:
    manifest, chunks, page_count = collect_chunks(settings)
    texts = [chunk.text for chunk in chunks]
    embeddings = embedding_provider.embed_texts(texts, batch_size=settings.batch_size)
    if embeddings.shape != (len(chunks), embedding_provider.dimension):
        raise IngestionError("Dimensão de embeddings incompatível com a quantidade de chunks.")

    vectorizer = TfidfVectorizer(strip_accents="unicode", lowercase=True, ngram_range=(1, 2))
    lexical_matrix = vectorizer.fit_transform(texts)

    index_root = settings.resolved_index_dir
    index_root.mkdir(parents=True, exist_ok=True)
    target = active_index_dir(index_root)

    with tempfile.TemporaryDirectory(prefix=".build-", dir=index_root) as tmp_name:
        tmp_path = Path(tmp_name)
        np.savez_compressed(tmp_path / "embeddings.npz", embeddings=embeddings)
        write_json(tmp_path / "metadata.json", [chunk.to_dict() for chunk in chunks])
        with (tmp_path / "lexical.pkl").open("wb") as file:
            pickle.dump({"vectorizer": vectorizer, "matrix": lexical_matrix}, file)
        write_json(
            tmp_path / "index_manifest.json",
            {
                "format_version": INDEX_FORMAT_VERSION,
                "corpus_fingerprint": corpus_fingerprint(manifest),
                "config_fingerprint": settings.index_config_fingerprint(),
                "embedding_model": settings.embedding_model,
                "embedding_dimension": embedding_provider.dimension,
                "documents": len(enabled_documents(manifest)),
                "pages": page_count,
                "chunks": len(chunks),
            },
        )
        validate_index(tmp_path, settings=settings)

        backup = index_root / "previous"
        old = index_root / ".old-active"
        if old.exists():
            shutil.rmtree(old)
        try:
            if target.exists():
                target.replace(old)
            tmp_path.replace(target)
            if backup.exists():
                shutil.rmtree(backup)
            if old.exists():
                old.replace(backup)
        except Exception:
            if target.exists() and not (target / "index_manifest.json").exists():
                shutil.rmtree(target, ignore_errors=True)
            if old.exists() and not target.exists():
                old.replace(target)
            raise

    return BuildSummary(
        documents=len(enabled_documents(manifest)),
        pages=page_count,
        chunks=len(chunks),
        embedding_dimension=embedding_provider.dimension,
        index_path=target,
        size_bytes=index_size_bytes(target),
    )


def validate_index(path: Path, settings: Settings | None = None) -> dict[str, Any]:
    required = ["embeddings.npz", "metadata.json", "lexical.pkl", "index_manifest.json"]
    for name in required:
        if not (path / name).is_file():
            raise IndexError(f"Artefato ausente no índice: {name}")

    manifest = read_json(path / "index_manifest.json")
    if manifest.get("format_version") != INDEX_FORMAT_VERSION:
        raise IndexError("Versão do formato do índice incompatível.")
    if settings and manifest.get("config_fingerprint") != settings.index_config_fingerprint():
        raise IndexError("Fingerprint de configuração incompatível com o índice.")

    embeddings = np.load(path / "embeddings.npz")["embeddings"]
    metadata = read_json(path / "metadata.json")
    if embeddings.ndim != 2:
        raise IndexError("Embeddings devem ser uma matriz 2D.")
    if len(metadata) != embeddings.shape[0]:
        raise IndexError("Quantidade de metadados não corresponde aos embeddings.")

    try:
        with (path / "lexical.pkl").open("rb") as file:
            lexical = pickle.load(file)
    except Exception as exc:
        raise IndexError("Artefato lexical corrompido.") from exc
    if "vectorizer" not in lexical or "matrix" not in lexical:
        raise IndexError("Artefato lexical incompleto.")
    if lexical["matrix"].shape[0] != embeddings.shape[0]:
        raise IndexError("Matriz lexical incompatível com embeddings.")

    return manifest
