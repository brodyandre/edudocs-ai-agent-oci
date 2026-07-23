#!/usr/bin/env python3
"""Sincroniza blocos de evidencias visuais no README."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
GUIDE_PATH = "docs/screenshot-guide.md"


@dataclass(frozen=True)
class EvidenceBlock:
    key: str
    path: str
    caption: str
    future: bool = False

    @property
    def start(self) -> str:
        return f"<!-- EVIDENCE:{self.key}:START -->"

    @property
    def end(self) -> str:
        return f"<!-- EVIDENCE:{self.key}:END -->"


EVIDENCE_BLOCKS: tuple[EvidenceBlock, ...] = (
    EvidenceBlock("HOME", "docs/evidence/home-hero.png", "Hero da interface de consulta documental."),
    EvidenceBlock(
        "ANSWER",
        "docs/evidence/answer-with-sources.png",
        "Resposta com fontes e paginas exibidas para o usuario.",
    ),
    EvidenceBlock(
        "UNSUPPORTED",
        "docs/evidence/unsupported-question.png",
        "Recusa segura quando o corpus nao sustenta a resposta.",
    ),
    EvidenceBlock(
        "DOCUMENTS",
        "docs/evidence/documents-panel.png",
        "Painel de documentos disponiveis no corpus ficticio.",
    ),
    EvidenceBlock(
        "ACTIONS",
        "docs/evidence/github-actions.png",
        "Workflows do GitHub Actions apos a validacao do projeto.",
    ),
    EvidenceBlock(
        "DOCKER",
        "docs/evidence/docker-smoke.png",
        "Validacao integrada da stack Docker local.",
    ),
    EvidenceBlock(
        "OCI_APP",
        "docs/evidence/oci-application.png",
        "Aplicacao publicada na OCI apos deploy real.",
        future=True,
    ),
    EvidenceBlock(
        "OCI_INSTANCE",
        "docs/evidence/oci-instance-running.png",
        "Instancia OCI em execucao apos provisionamento real.",
        future=True,
    ),
)


def evidence_content(block: EvidenceBlock, root: Path = ROOT) -> str:
    if (root / block.path).is_file():
        return f"![{block.caption}]({block.path})\n\n_{block.caption}_"

    scope = "reservada para etapa futura" if block.future else "pendente"
    return (
        f"> **Captura {scope}:** `{block.path}`.\n"
        f"> Consulte o guia em `{GUIDE_PATH}`."
    )


def replace_block(text: str, block: EvidenceBlock, root: Path = ROOT) -> str:
    start_count = text.count(block.start)
    end_count = text.count(block.end)
    if start_count != 1 or end_count != 1:
        raise ValueError(
            f"Marcadores invalidos para {block.key}: START={start_count}, END={end_count}."
        )

    start_index = text.index(block.start) + len(block.start)
    end_index = text.index(block.end)
    if start_index > end_index:
        raise ValueError(f"Marcadores fora de ordem para {block.key}.")

    replacement = "\n" + evidence_content(block, root) + "\n"
    return text[:start_index] + replacement + text[end_index:]


def sync_readme(readme_path: Path = README_PATH, root: Path = ROOT) -> bool:
    text = readme_path.read_text(encoding="utf-8")
    updated = text
    for block in EVIDENCE_BLOCKS:
        updated = replace_block(updated, block, root)

    if updated == text:
        return False

    readme_path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atualiza blocos de evidencias do README.")
    parser.add_argument("--readme", type=Path, default=README_PATH)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        changed = sync_readme(args.readme, args.root)
    except (OSError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print("README sincronizado." if changed else "README ja estava sincronizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
