from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_TRACKED_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_LARGE_PREFIXES = ("corpus/documents/",)
ALLOWED_ENV_EXAMPLES = {".env.example", "apps/api/.env.example", "apps/web/.env.example"}

FORBIDDEN_EXACT = {
    ".env",
    ".env.local",
    ".env.production",
    "terraform.tfvars",
    "tfplan",
    "oci_config",
}
FORBIDDEN_SUFFIXES = (
    ".pem",
    ".tfstate",
    ".tfplan",
    ".kubeconfig",
)
FORBIDDEN_PARTS = {
    "node_modules",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    "__pycache__",
}
SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    (
        "groq-api-key-value",
        re.compile(r"\bGROQ_API_KEY\s*=\s*(?!$|fake\b|example\b|changeme\b|your_|<)[^\s#]+", re.IGNORECASE),
    ),
    ("oci-ocid", re.compile(r"\bocid1\.(?:tenancy|user|compartment|instance|vcn|subnet)\.[A-Za-z0-9_.-]+")),
)
TEXT_SUFFIXES = {
    ".css",
    ".dockerignore",
    ".env.example",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    guidance: str


def tracked_files(root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        text=False,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def is_text_file(path: Path) -> bool:
    return path.name in {".dockerignore", "Makefile"} or path.suffix in TEXT_SUFFIXES


def detect_forbidden_paths(paths: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        name = Path(normalized).name
        parts = set(Path(normalized).parts)
        if normalized in ALLOWED_ENV_EXAMPLES:
            continue
        if normalized.startswith("corpus/index/") and normalized != "corpus/index/.gitkeep":
            findings.append(Finding(normalized, "versioned-index", "Remova indices gerados do controle de versao."))
        if normalized in FORBIDDEN_EXACT or name in FORBIDDEN_EXACT:
            findings.append(Finding(normalized, "forbidden-file", "Remova o arquivo sensivel ou gerado."))
        if any(name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            findings.append(Finding(normalized, "forbidden-extension", "Remova credenciais, planos ou state do Git."))
        if parts & FORBIDDEN_PARTS:
            findings.append(Finding(normalized, "generated-directory", "Nao versione dependencias, caches ou builds locais."))
    return findings


def validate_json(paths: list[str], root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.endswith(".json"):
            continue
        try:
            json.loads((root / path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            findings.append(Finding(path, "invalid-json", "Corrija a sintaxe JSON."))
    return findings


def detect_large_files(paths: list[str], root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        file_path = root / path
        if not file_path.is_file():
            continue
        if path.startswith(ALLOWED_LARGE_PREFIXES):
            continue
        if file_path.stat().st_size > MAX_TRACKED_FILE_BYTES:
            findings.append(Finding(path, "large-file", "Confirme necessidade ou remova arquivo grande inesperado."))
    return findings


def detect_secrets(paths: list[str], root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if path in ALLOWED_ENV_EXAMPLES:
            continue
        file_path = root / path
        if not file_path.is_file() or not is_text_file(file_path):
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(Finding(path, kind, "Remova o segredo e rotacione a credencial se ela for real."))
    return findings


def validate_readme_links(root: Path = ROOT) -> list[Finding]:
    readme = root / "README.md"
    if not readme.is_file():
        return [Finding("README.md", "missing-readme", "Restaure o README principal.")]
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    findings: list[Finding] = []
    for raw_link in pattern.findall(text):
        link = raw_link.strip()
        if not link or re.match(r"^[a-z][a-z0-9+.-]*:", link, re.IGNORECASE) or link.startswith("#"):
            continue
        target = link.split("#", 1)[0]
        if target and not (root / target).exists():
            findings.append(Finding("README.md", "broken-relative-link", f"Corrija link relativo: {target}"))
    return findings


def collect_findings(root: Path = ROOT) -> list[Finding]:
    paths = tracked_files(root)
    findings: list[Finding] = []
    findings.extend(detect_forbidden_paths(paths))
    findings.extend(validate_json(paths, root))
    findings.extend(detect_large_files(paths, root))
    findings.extend(detect_secrets(paths, root))
    findings.extend(validate_readme_links(root))
    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.path}: {finding.kind}: {finding.guidance}")


def main() -> int:
    findings = collect_findings(ROOT)
    if findings:
        print_findings(findings)
        return 1
    print("OK: higiene do repositorio validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
