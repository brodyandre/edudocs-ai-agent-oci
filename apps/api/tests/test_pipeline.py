from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import fitz
import httpx
import pytest

from app.core.config import Settings
from app.core.errors import DocumentExtractionError, IndexError, ManifestError
from app.documents.manifest import corpus_fingerprint, load_manifest, sha256_file
from app.documents.pdf import extract_pdf_pages
from app.ingestion.chunking import chunk_pages, content_hash
from app.ingestion.embeddings import FakeEmbeddingProvider
from app.ingestion.index import active_index_dir, build_index, validate_index
from app.ingestion.normalization import normalize_pages, normalize_text
from app.main import create_app
from app.retrieval.search import LocalIndex


def write_pdf(path: Path, title: str, pages: list[str]) -> None:
    pdf = fitz.open()
    for text in pages:
        page = pdf.new_page()
        page.insert_text((72, 72), f"{title}\n{text}", fontsize=12)
    pdf.save(path)
    pdf.close()


def write_manifest(repo: Path, docs: list[dict[str, Any]]) -> Path:
    manifest_path = repo / "corpus" / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "Teste",
                "version": "1.0",
                "generated_by": "tests",
                "documents": docs,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


@pytest.fixture()
def tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "corpus" / "sources").mkdir(parents=True)
    (repo / "corpus" / "documents").mkdir(parents=True)
    (repo / "corpus" / "index").mkdir(parents=True)
    source = repo / "corpus" / "sources" / "doc.md"
    source.write_text(
        "# Documento de Teste\n\n**Identificador:** doc\n**Versão:** 1.0\n"
        "**Data de vigência:** 2026-07-01\n\n## Sumário\n\n1. Regras\n",
        encoding="utf-8",
    )
    pdf = repo / "corpus" / "documents" / "doc.pdf"
    write_pdf(
        pdf,
        "Documento de Teste",
        [
            "1. Regras\nA matrícula dura 10 dias. O suporte responde rápido.",
            "2. Certificados\nO certificado exige 70 por cento de aproveitamento.",
        ],
    )
    write_manifest(
        repo,
        [
            {
                "id": "doc",
                "title": "Documento de Teste",
                "version": "1.0",
                "effective_date": "2026-07-01",
                "source_path": "corpus/sources/doc.md",
                "pdf_path": "corpus/documents/doc.pdf",
                "category": "teste",
                "language": "pt-BR",
                "sha256": sha256_file(pdf),
                "enabled": True,
            }
        ],
    )
    return repo


@pytest.fixture()
def tiny_settings(tiny_repo: Path) -> Settings:
    return Settings(
        root_dir=tiny_repo,
        manifest_path=Path("corpus/manifest.json"),
        documents_dir=Path("corpus/documents"),
        index_dir=Path("corpus/index"),
        embedding_provider="fake",
        fake_embedding_dimension=16,
        chunk_size=180,
        chunk_overlap=20,
        batch_size=4,
        default_top_k=3,
        testing=True,
    )


def test_manifest_valido(tiny_settings: Settings) -> None:
    manifest = load_manifest(tiny_settings.resolved_manifest_path, tiny_settings.repo_root)
    assert manifest.documents[0].id == "doc"


def test_manifest_invalido(tiny_repo: Path) -> None:
    (tiny_repo / "corpus" / "manifest.json").write_text('{"documents": "x"}\n', encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(tiny_repo / "corpus" / "manifest.json", tiny_repo)


def test_manifest_id_duplicado(tiny_repo: Path) -> None:
    manifest = json.loads((tiny_repo / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    manifest["documents"].append(dict(manifest["documents"][0]))
    (tiny_repo / "corpus" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ManifestError, match="duplicados"):
        load_manifest(tiny_repo / "corpus" / "manifest.json", tiny_repo)


def test_manifest_caminho_invalido(tiny_repo: Path) -> None:
    manifest = json.loads((tiny_repo / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    manifest["documents"][0]["pdf_path"] = "../fora.pdf"
    (tiny_repo / "corpus" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ManifestError, match="fora"):
        load_manifest(tiny_repo / "corpus" / "manifest.json", tiny_repo)


def test_manifest_hash_divergente(tiny_repo: Path) -> None:
    manifest = json.loads((tiny_repo / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    manifest["documents"][0]["sha256"] = "0" * 64
    (tiny_repo / "corpus" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ManifestError, match="SHA-256"):
        load_manifest(tiny_repo / "corpus" / "manifest.json", tiny_repo)


def test_pdf_corrompido(tiny_repo: Path) -> None:
    pdf = tiny_repo / "corpus" / "documents" / "doc.pdf"
    pdf.write_bytes(b"nao sou pdf")
    manifest = load_manifest(
        tiny_repo / "corpus" / "manifest.json",
        tiny_repo,
        validate_hashes=False,
    )
    with pytest.raises(DocumentExtractionError, match="corrompido"):
        extract_pdf_pages(manifest.documents[0], tiny_repo)


def test_extracao_por_pagina(tiny_settings: Settings) -> None:
    manifest = load_manifest(tiny_settings.resolved_manifest_path, tiny_settings.repo_root)
    pages = extract_pdf_pages(manifest.documents[0], tiny_settings.repo_root)
    assert [page.page_number for page in pages] == [1, 2]
    assert pages[0].document_version == "1.0"


def test_normalizacao_preserva_texto_e_remove_rodape() -> None:
    text = "EduDocs Academy\nTítulo · v1.0\nPágina 1\n\n1. Item\n  Valor   com espaços\n"
    assert normalize_text(text) == "1. Item\nValor com espaços"


def test_chunking_deterministico_metadados_e_hash(tiny_settings: Settings) -> None:
    manifest = load_manifest(tiny_settings.resolved_manifest_path, tiny_settings.repo_root)
    pages = normalize_pages(extract_pdf_pages(manifest.documents[0], tiny_settings.repo_root))
    first = chunk_pages(pages, tiny_settings.chunk_size, tiny_settings.chunk_overlap)
    second = chunk_pages(pages, tiny_settings.chunk_size, tiny_settings.chunk_overlap)
    assert first == second
    assert all(chunk.text for chunk in first)
    assert first[0].document_id == "doc"
    assert first[0].content_hash == content_hash(first[0].text)


def test_chunk_vazio_nao_eh_criado() -> None:
    assert chunk_pages([], chunk_size=120, chunk_overlap=0) == []


def test_fingerprint(tiny_settings: Settings) -> None:
    manifest = load_manifest(tiny_settings.resolved_manifest_path, tiny_settings.repo_root)
    assert len(corpus_fingerprint(manifest)) == 64
    assert len(tiny_settings.index_config_fingerprint()) == 64


def test_embedding_falso_e_normalizado() -> None:
    provider = FakeEmbeddingProvider(dimension=8)
    vectors = provider.embed_texts(["matrícula suporte", "certificado"], batch_size=2)
    assert vectors.shape == (2, 8)
    assert pytest.approx(float((vectors[0] ** 2).sum()), rel=1e-6) == 1.0


def test_publicacao_atomica(tiny_settings: Settings) -> None:
    summary = build_index(tiny_settings, FakeEmbeddingProvider(dimension=16))
    assert summary.chunks > 0
    assert (active_index_dir(tiny_settings.resolved_index_dir) / "index_manifest.json").is_file()


def test_preserva_indice_anterior_em_falha(tiny_settings: Settings) -> None:
    build_index(tiny_settings, FakeEmbeddingProvider(dimension=16))
    marker = active_index_dir(tiny_settings.resolved_index_dir) / "marker.txt"
    marker.write_text("anterior", encoding="utf-8")

    class BrokenProvider(FakeEmbeddingProvider):
        def embed_texts(self, texts: list[str], batch_size: int):  # type: ignore[no-untyped-def]
            raise RuntimeError("falha simulada")

    with pytest.raises(RuntimeError):
        build_index(tiny_settings, BrokenProvider(dimension=16))
    assert marker.read_text(encoding="utf-8") == "anterior"


def test_indice_corrompido(tiny_settings: Settings) -> None:
    build_index(tiny_settings, FakeEmbeddingProvider(dimension=16))
    (active_index_dir(tiny_settings.resolved_index_dir) / "lexical.pkl").write_bytes(b"quebrado")
    with pytest.raises(IndexError):
        validate_index(active_index_dir(tiny_settings.resolved_index_dir), settings=tiny_settings)


def test_busca_semantica_e_lexical(tiny_settings: Settings) -> None:
    build_index(tiny_settings, FakeEmbeddingProvider(dimension=16))
    index = LocalIndex.load(tiny_settings)
    results = index.search(
        "certificado aproveitamento",
        FakeEmbeddingProvider(dimension=16),
        top_k=2,
        batch_size=2,
    )
    assert results
    assert results[0].score >= results[-1].score
    assert any("certificado" in result.text.lower() for result in results)


@pytest.mark.anyio
async def test_api_health() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_api_cors_permite_frontend_local() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.anyio
async def test_api_ready_e_documents(
    tiny_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_index(tiny_settings, FakeEmbeddingProvider(dimension=16))
    import app.api.routes as routes

    monkeypatch.setattr(routes, "get_settings", lambda: tiny_settings)
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ready = await client.get("/ready")
        documents = await client.get("/api/documents")
    assert ready.status_code == 200
    assert ready.json()["chunks"] > 0
    assert documents.status_code == 200
    assert documents.json()["documents"][0]["id"] == "doc"


@pytest.mark.anyio
async def test_api_ready_sem_indice(
    tiny_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.rmtree(tiny_settings.resolved_index_dir)
    tiny_settings.resolved_index_dir.mkdir()
    import app.api.routes as routes

    monkeypatch.setattr(routes, "get_settings", lambda: tiny_settings)
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
