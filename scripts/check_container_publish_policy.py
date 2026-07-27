#!/usr/bin/env python3
"""Audita a politica estatica de publicacao multiarch no GHCR."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE = Path(".github") / "workflows" / "publish-images.yml"
COMPOSE_PROD_RELATIVE = Path("docker-compose.prod.yml")
EXPECTED_IMAGES = {
    "ghcr.io/brodyandre/edudocs-ai-api",
    "ghcr.io/brodyandre/edudocs-ai-web",
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    guidance: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def workflow_files(root: Path) -> list[Path]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    return sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")])


def find_workflow_risks(root: Path = ROOT) -> list[Finding]:
    workflow = root / WORKFLOW_RELATIVE
    text = read_text(workflow)
    findings: list[Finding] = []
    if not text:
        return [Finding(".github/workflows/publish-images.yml", "missing-workflow", "Crie o workflow de publicacao.")]

    forbidden_triggers = ("push:", "pull_request:", "pull_request_target:", "schedule:")
    workflow_path = str(workflow.relative_to(root))
    for trigger in forbidden_triggers:
        if re.search(rf"^  {re.escape(trigger)}\s*$", text, flags=re.MULTILINE):
            findings.append(Finding(workflow_path, "forbidden-trigger", f"Remova {trigger}"))
    if not re.search(r"^\s*workflow_dispatch\s*:", text, flags=re.MULTILINE):
        findings.append(Finding(workflow_path, "missing-workflow-dispatch", "Use apenas workflow_dispatch."))
    if "publish_main_alias" not in text:
        findings.append(Finding(workflow_path, "missing-input", "Inclua input publish_main_alias."))
    if "timeout-minutes: 60" not in text:
        findings.append(Finding(workflow_path, "missing-timeout", "Defina timeout de 60 minutos."))
    if "group: publish-images-${{ github.ref }}" not in text or "cancel-in-progress: false" not in text:
        findings.append(Finding(workflow_path, "missing-concurrency", "Configure concurrency da publicacao."))
    if not re.search(r"contents:\s*read", text):
        findings.append(Finding(workflow_path, "missing-contents-read", "Use contents: read."))
    if not re.search(r"packages:\s*write", text):
        findings.append(Finding(workflow_path, "missing-packages-write", "Use packages: write apenas neste workflow."))
    if re.search(r"contents:\s*write|write-all", text):
        findings.append(Finding(workflow_path, "excessive-permission", "Nao use contents: write ou write-all."))
    if re.search(r"(PAT|GHCR_TOKEN|CR_PAT|PERSONAL_ACCESS_TOKEN|github_pat_|ghp_)", text):
        findings.append(Finding(workflow_path, "pat-reference", "Use somente secrets.GITHUB_TOKEN."))
    if "secrets.GITHUB_TOKEN" not in text or "docker/login-action@v3" not in text:
        findings.append(Finding(workflow_path, "missing-github-token-login", "Login GHCR deve usar docker/login-action com GITHUB_TOKEN."))
    if "latest" in text.lower():
        findings.append(Finding(workflow_path, "latest-reference", "Nao publique latest."))
    if "linux/amd64,linux/arm64" not in text:
        findings.append(Finding(workflow_path, "missing-platforms", "Publique linux/amd64 e linux/arm64."))
    if "sha-${{ github.sha }}" not in text:
        findings.append(Finding(workflow_path, "missing-sha-tag", "Publique tag baseada no SHA completo."))
    if "org.opencontainers.image.revision" not in text:
        findings.append(Finding(workflow_path, "missing-oci-labels", "Inclua labels OCI."))
    if "imagetools inspect" not in text or "ANON_DOCKER_CONFIG" not in text:
        findings.append(Finding(workflow_path, "missing-anonymous-inspect", "Valide pull anonimo por digest."))
    if "scripts/smoke_test.py" not in text or "docker compose" not in text:
        findings.append(Finding(workflow_path, "missing-smoke", "Execute smoke pos-publicacao."))
    if "apps/api/Dockerfile" not in text or "apps/web/Dockerfile" not in text or "context: ." not in text:
        findings.append(Finding(workflow_path, "invalid-build-context", "Use Dockerfiles corretos com contexto raiz."))
    if "GROQ_API_KEY" in text or re.search(r"\bOCI_", text):
        findings.append(Finding(workflow_path, "secret-reference", "Nao use segredo Groq ou OCI no workflow."))
    for image in re.findall(r"ghcr\.io/brodyandre/[a-z0-9-]+", text):
        if image not in EXPECTED_IMAGES:
            findings.append(Finding(workflow_path, "unexpected-image", f"Imagem nao aprovada: {image}."))
    if re.search(r"ghcr\.io/.+nginx|file:\s*.*nginx", text, flags=re.IGNORECASE):
        findings.append(Finding(workflow_path, "nginx-publish", "Nao publique imagem Nginx."))
    if "@${API_DIGEST}" not in text or "@${WEB_DIGEST}" not in text:
        findings.append(Finding(workflow_path, "missing-digest-ref", "Use referencias por digest nas validacoes."))
    return findings


def find_cross_workflow_risks(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in workflow_files(root):
        if path == root / WORKFLOW_RELATIVE:
            continue
        text = read_text(path)
        if re.search(r"packages:\s*write", text):
            findings.append(Finding(str(path.relative_to(root)), "packages-write-outside-publish", "Somente publish-images.yml pode escrever packages."))
    return findings


def find_compose_risks(root: Path = ROOT) -> list[Finding]:
    text = read_text(root / COMPOSE_PROD_RELATIVE)
    findings: list[Finding] = []
    if not text:
        return [Finding("docker-compose.prod.yml", "missing-compose", "Compose de producao ausente.")]
    for var in ("API_IMAGE_REF", "WEB_IMAGE_REF"):
        if f"${{{var}:?" not in text:
            findings.append(Finding("docker-compose.prod.yml", "missing-image-ref", f"Exija {var} por digest."))
    if "IMAGE_TAG" in text or "latest" in text.lower():
        findings.append(Finding("docker-compose.prod.yml", "mutable-reference", "Nao use IMAGE_TAG nem latest em producao."))
    for port in ('"3000:', '"8000:', "3000:3000", "8000:8000"):
        if port in text:
            findings.append(Finding("docker-compose.prod.yml", "internal-port-exposed", "Nao exponha 3000 ou 8000."))
    if "${NGINX_PORT:-8080}:8080" not in text:
        findings.append(Finding("docker-compose.prod.yml", "nginx-port", "Preserve Nginx em 8080."))
    for image in EXPECTED_IMAGES:
        if image in text:
            findings.append(Finding("docker-compose.prod.yml", "hardcoded-image", "Use API_IMAGE_REF/WEB_IMAGE_REF no Compose."))
    return findings


def collect_findings(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(find_workflow_risks(root))
    findings.extend(find_cross_workflow_risks(root))
    findings.extend(find_compose_risks(root))
    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.path}: {finding.kind}: {finding.guidance}")


def main() -> int:
    findings = collect_findings(ROOT)
    if findings:
        print_findings(findings)
        return 1
    print("OK: politica de publicacao de containers validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
