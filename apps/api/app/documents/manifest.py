from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.core.errors import ManifestError


class ManifestDocument(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: str = Field(min_length=1)
    effective_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_path: Path
    pdf_path: Path
    category: str = Field(min_length=1)
    language: str = "pt-BR"
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    enabled: bool


class CorpusManifest(BaseModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    generated_by: str = Field(min_length=1)
    documents: list[ManifestDocument]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_inside_repo(repo_root: Path, relative_path: Path) -> Path:
    if relative_path.is_absolute():
        raise ManifestError(f"Caminho absoluto não permitido no manifesto: {relative_path}")
    resolved = (repo_root / relative_path).resolve()
    if not resolved.is_relative_to(repo_root):
        raise ManifestError(f"Caminho fora do repositório no manifesto: {relative_path}")
    return resolved


def load_manifest(
    manifest_path: Path, repo_root: Path, validate_hashes: bool = True
) -> CorpusManifest:
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = CorpusManifest.model_validate(raw)
    except FileNotFoundError as exc:
        raise ManifestError(f"Manifesto não encontrado: {manifest_path}") from exc
    except UnicodeDecodeError as exc:
        raise ManifestError("Manifesto deve estar em UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifesto JSON inválido: {exc}") from exc
    except ValidationError as exc:
        raise ManifestError(f"Schema do manifesto inválido: {exc}") from exc

    ids = [document.id for document in manifest.documents]
    duplicates = sorted({doc_id for doc_id in ids if ids.count(doc_id) > 1})
    if duplicates:
        raise ManifestError(f"IDs duplicados no manifesto: {', '.join(duplicates)}")

    for document in manifest.documents:
        source_path = ensure_inside_repo(repo_root, document.source_path)
        pdf_path = ensure_inside_repo(repo_root, document.pdf_path)
        if not source_path.is_file():
            raise ManifestError(f"Fonte Markdown ausente: {document.source_path}")
        if not pdf_path.is_file():
            raise ManifestError(f"PDF ausente: {document.pdf_path}")
        if validate_hashes and sha256_file(pdf_path) != document.sha256:
            raise ManifestError(f"Hash SHA-256 divergente para {document.id}.")

    return manifest


def enabled_documents(manifest: CorpusManifest) -> list[ManifestDocument]:
    return [document for document in manifest.documents if document.enabled]


def corpus_fingerprint(manifest: CorpusManifest) -> str:
    payload = [
        {
            "id": document.id,
            "version": document.version,
            "pdf_path": str(document.pdf_path),
            "sha256": document.sha256,
            "enabled": document.enabled,
        }
        for document in sorted(manifest.documents, key=lambda item: item.id)
    ]
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
