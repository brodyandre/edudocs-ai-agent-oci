#!/usr/bin/env python3
"""Valida consistencia basica do README principal."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
EVIDENCE_KEYS = (
    "HOME",
    "ANSWER",
    "UNSUPPORTED",
    "DOCUMENTS",
    "ACTIONS",
    "DOCKER",
    "OCI_APP",
    "OCI_INSTANCE",
)


@dataclass(frozen=True)
class Finding:
    kind: str
    message: str


def github_anchor(heading: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def markdown_links(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text)]


def markdown_images(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text)]


def collect_headings(text: str) -> set[str]:
    headings: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.add(github_anchor(match.group(2)))
    return headings


def validate_readme(text: str, root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    headings = collect_headings(text)

    if "\ufeff" in text:
        findings.append(Finding("utf8-bom", "README contem BOM UTF-8."))
    if "/home/" in text or "C:\\Users" in text:
        findings.append(Finding("absolute-path", "README contem caminho absoluto local."))
    if "deploy OCI conclu" in text.lower() or "oci ativa" in text.lower():
        findings.append(Finding("oci-deploy-claim", "README sugere deploy OCI concluido."))
    if "badge.svg" in text and "deploy" in text.lower() and "actions/workflows" not in text:
        findings.append(Finding("deploy-badge", "README parece conter badge de deploy inexistente."))

    for key in EVIDENCE_KEYS:
        start = f"<!-- EVIDENCE:{key}:START -->"
        end = f"<!-- EVIDENCE:{key}:END -->"
        if text.count(start) != 1 or text.count(end) != 1:
            findings.append(Finding("evidence-marker", f"Marcadores invalidos para {key}."))

    for link in markdown_links(text):
        if not link or re.match(r"^[a-z][a-z0-9+.-]*:", link, re.IGNORECASE):
            continue
        if link.startswith("#"):
            anchor = github_anchor(link[1:])
            if anchor not in headings:
                findings.append(Finding("broken-anchor", f"Ancora inexistente: {link}"))
            continue
        target, _, anchor = link.partition("#")
        if target and not (root / target).exists():
            findings.append(Finding("broken-link", f"Link relativo inexistente: {target}"))
        if anchor and github_anchor(anchor) not in headings and target in {"", "README.md"}:
            findings.append(Finding("broken-anchor", f"Ancora inexistente: #{anchor}"))

    for image in markdown_images(text):
        target = image.split("#", 1)[0]
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
            continue
        if target and not (root / target).is_file():
            findings.append(Finding("broken-image", f"Imagem referenciada nao existe: {target}"))

    index_match = re.search(r"## Índice\s+(.+?)(?:\n##\s)", text, flags=re.DOTALL)
    if not index_match:
        findings.append(Finding("missing-index", "Indice remissivo ausente."))
    else:
        index_links = markdown_links(index_match.group(1))
        if len(index_links) < 10:
            findings.append(Finding("short-index", "Indice contem poucas secoes."))

    if "[Voltar ao índice](#índice)" not in text:
        findings.append(Finding("missing-backlinks", "Links de retorno ao indice ausentes."))

    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Valida README.md.")
    parser.add_argument("--readme", type=Path, default=README_PATH)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raw = args.readme.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise UnicodeError("BOM UTF-8 encontrado.")
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"ERRO: README invalido: {exc}", file=sys.stderr)
        return 1

    findings = validate_readme(text, args.root)
    if findings:
        for finding in findings:
            print(f"{finding.kind}: {finding.message}")
        return 1

    print("OK: README validado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
