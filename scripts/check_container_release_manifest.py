#!/usr/bin/env python3
"""Valida o manifesto sanitizado de publicacao das imagens GHCR."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_REPOSITORY = "brodyandre/edudocs-ai-agent-oci"
EXPECTED_API_IMAGE = "ghcr.io/brodyandre/edudocs-ai-api"
EXPECTED_WEB_IMAGE = "ghcr.io/brodyandre/edudocs-ai-web"
EXPECTED_PLATFORMS = ["linux/amd64", "linux/arm64"]
DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
COMMIT_PATTERN = re.compile(r"^[a-f0-9]{40}$")
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SECRET_PATTERNS = (
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\bocid1\.[A-Za-z0-9_.-]+"),
    re.compile(r"\bGROQ_API_KEY\b", re.IGNORECASE),
    re.compile(r"\b(password|secret|token)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    guidance: str


def validate_image_block(
    manifest: dict[str, Any], key: str, expected_image: str
) -> list[Finding]:
    findings: list[Finding] = []
    block = manifest.get(key)
    if not isinstance(block, dict):
        return [Finding(key, "missing-image-block", f"Bloco {key} ausente.")]

    digest = block.get("digest")
    immutable_ref = block.get("immutable_ref")
    image = block.get("image")
    expected_ref = f"{expected_image}@{digest}"

    if image != expected_image:
        findings.append(Finding(f"{key}.image", "unexpected-image", expected_image))
    if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
        findings.append(Finding(f"{key}.digest", "invalid-digest", "Use sha256 com 64 caracteres hexadecimais."))
    if immutable_ref != expected_ref:
        findings.append(Finding(f"{key}.immutable_ref", "invalid-immutable-ref", "Referencia deve combinar imagem e digest."))
    return findings


def validate_runtime(manifest: dict[str, Any]) -> list[Finding]:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        return [Finding("runtime", "missing-runtime", "Bloco runtime ausente.")]
    expected = {
        "public_entry_port": 80,
        "load_balancer_backend_port": 8080,
        "health_path": "/health",
    }
    findings: list[Finding] = []
    for key, value in expected.items():
        if runtime.get(key) != value:
            findings.append(Finding(f"runtime.{key}", "invalid-runtime", f"Valor esperado: {value}."))
    return findings


def validate_no_sensitive_content(manifest: dict[str, Any]) -> list[Finding]:
    text = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    findings: list[Finding] = []
    if "latest" in text.lower():
        findings.append(Finding("manifest", "latest-reference", "Nao use latest no manifesto."))
    if IP_PATTERN.search(text):
        findings.append(Finding("manifest", "ip-address", "Nao grave IP no manifesto."))
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(Finding("manifest", "sensitive-content", "Remova token, segredo, chave, OCID ou GROQ_API_KEY."))
            break
    return findings


def validate_manifest(manifest: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if manifest.get("schema_version") != 1:
        findings.append(Finding("schema_version", "invalid-schema", "schema_version deve ser 1."))
    if manifest.get("repository") != EXPECTED_REPOSITORY:
        findings.append(Finding("repository", "invalid-repository", EXPECTED_REPOSITORY))
    if not isinstance(manifest.get("source_commit"), str) or not COMMIT_PATTERN.fullmatch(
        manifest.get("source_commit", "")
    ):
        findings.append(Finding("source_commit", "invalid-commit", "Use SHA completo de 40 caracteres."))
    if manifest.get("platforms") != EXPECTED_PLATFORMS:
        findings.append(Finding("platforms", "invalid-platforms", "Use exatamente linux/amd64 e linux/arm64."))
    if not manifest.get("created_at"):
        findings.append(Finding("created_at", "missing-created-at", "Informe a data de geracao."))
    if not str(manifest.get("workflow_run", "")).strip():
        findings.append(Finding("workflow_run", "missing-workflow-run", "Informe a execucao do workflow."))

    findings.extend(validate_image_block(manifest, "api", EXPECTED_API_IMAGE))
    findings.extend(validate_image_block(manifest, "web", EXPECTED_WEB_IMAGE))
    findings.extend(validate_runtime(manifest))
    findings.extend(validate_no_sensitive_content(manifest))
    return findings


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("manifesto precisa ser um objeto JSON")
    return data


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.path}: {finding.kind}: {finding.guidance}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: check_container_release_manifest.py MANIFEST_JSON", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(Path(argv[1]))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"manifest: invalid-json: {exc}", file=sys.stderr)
        return 1
    findings = validate_manifest(manifest)
    if findings:
        print_findings(findings)
        return 1
    print("OK: manifesto de release de containers validado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
