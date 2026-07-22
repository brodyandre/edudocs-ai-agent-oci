#!/usr/bin/env python3
"""Valida arquivos textuais UTF-8 sem expor conteudo."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".next",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".terraform",
    ".venv",
    "__pycache__",
    "build",
    "cache",
    "dist",
    "env",
    "htmlcov",
    "models",
    "node_modules",
    "out",
    "tmp",
    "venv",
}

IGNORED_PATHS = {
    Path("corpus/index"),
}

BINARY_EXTENSIONS = {
    ".7z",
    ".avif",
    ".bin",
    ".bmp",
    ".bz2",
    ".class",
    ".db",
    ".dll",
    ".doc",
    ".docx",
    ".exe",
    ".faiss",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".lock",
    ".mp3",
    ".mp4",
    ".o",
    ".pdf",
    ".png",
    ".pyc",
    ".pyo",
    ".rar",
    ".sqlite",
    ".tar",
    ".tgz",
    ".tiff",
    ".wasm",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".zip",
}


def is_ignored(path: Path) -> bool:
    relative = path.relative_to(ROOT)

    if any(part in IGNORED_DIRS for part in relative.parts):
        return True

    return any(relative == ignored or ignored in relative.parents for ignored in IGNORED_PATHS)


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return False

    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False

    return b"\x00" not in chunk


def validate_file(path: Path) -> list[str]:
    problems: list[str] = []

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [f"erro de leitura: {exc}"]

    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("BOM UTF-8 inesperado")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        problems.append(f"falha de decodificacao UTF-8 na posicao {exc.start}")
        return problems

    if "\ufffd" in text:
        problems.append("caractere de substituicao U+FFFD encontrado")

    return problems


def main() -> int:
    invalid: list[tuple[Path, list[str]]] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or is_ignored(path) or not is_probably_text(path):
            continue

        problems = validate_file(path)
        if problems:
            invalid.append((path.relative_to(ROOT), problems))

    if not invalid:
        print("OK: todos os arquivos textuais verificados estao em UTF-8 sem BOM.")
        return 0

    print("Arquivos invalidos encontrados:")
    for path, problems in invalid:
        print(f"- {path}: {'; '.join(problems)}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
