from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.core.errors import EduDocsError
from app.documents.manifest import enabled_documents, load_manifest
from app.ingestion.index import active_index_dir, build_index, index_size_bytes, validate_index
from app.ingestion.provider_factory import create_embedding_provider


def command_build(settings: Settings) -> int:
    provider = create_embedding_provider(settings)
    summary = build_index(settings, provider)
    print("Índice construído com sucesso.")
    print(f"documentos={summary.documents}")
    print(f"páginas={summary.pages}")
    print(f"chunks={summary.chunks}")
    print(f"dimensão_embeddings={summary.embedding_dimension}")
    print(f"diretório={summary.index_path.relative_to(settings.repo_root)}")
    print(f"tamanho_bytes={summary.size_bytes}")
    return 0


def command_validate(settings: Settings) -> int:
    manifest = validate_index(active_index_dir(settings.resolved_index_dir), settings=settings)
    print("Índice válido.")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def command_inspect(settings: Settings) -> int:
    manifest = load_manifest(settings.resolved_manifest_path, settings.repo_root)
    index_path = active_index_dir(settings.resolved_index_dir)
    try:
        index_manifest = validate_index(index_path, settings=settings)
        index_status = "válido"
    except EduDocsError as exc:
        index_manifest = {"erro": str(exc)}
        index_status = "inválido"

    print("Corpus:")
    print(f"- documentos_habilitados={len(enabled_documents(manifest))}")
    print("Índice:")
    print(f"- status={index_status}")
    print(f"- diretório={Path(index_path).relative_to(settings.repo_root)}")
    print(f"- tamanho_bytes={index_size_bytes(index_path)}")
    print(json.dumps(index_manifest, ensure_ascii=False, indent=2))
    return 0 if index_status == "válido" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI de ingestão do EduDocs AI")
    parser.add_argument("command", choices=["build", "validate", "inspect"])
    args = parser.parse_args()
    settings = Settings()

    try:
        if args.command == "build":
            return command_build(settings)
        if args.command == "validate":
            return command_validate(settings)
        if args.command == "inspect":
            return command_inspect(settings)
    except EduDocsError as exc:
        print(f"ERRO: {exc}")
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
