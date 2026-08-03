#!/usr/bin/env python3
"""Valida os templates declarativos de bootstrap da aplicacao OCI."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOUD_INIT_DIR = ROOT / "infrastructure" / "cloud-init"

API_IMAGE_REF = (
    "ghcr.io/brodyandre/edudocs-ai-api@sha256:"
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)
WEB_IMAGE_REF = (
    "ghcr.io/brodyandre/edudocs-ai-web@sha256:"
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
)
NGINX_IMAGE_REF = "nginxinc/nginx-unprivileged:1.27.4-alpine"

REQUIRED_FILES = {
    "app-server.yaml.tftpl",
    "docker-compose.prod.yaml.tftpl",
    "nginx.conf.tftpl",
    "runtime.env.tftpl",
    "edudocs-compose.service.tftpl",
}

FORBIDDEN_PATTERNS = {
    "docker-login": re.compile(r"\bdocker\s+login\b", re.IGNORECASE),
    "git-clone": re.compile(r"\bgit\s+clone\b", re.IGNORECASE),
    "latest-reference": re.compile(r"(?<![A-Za-z0-9_-])latest(?![A-Za-z0-9_-])", re.IGNORECASE),
    "github-token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    "github-pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "groq-secret": re.compile(r"\bGROQ_API_KEY\b", re.IGNORECASE),
    "real-ocid": re.compile(r"\bocid1\.[A-Za-z0-9_.-]+"),
    "curl-pipe-shell": re.compile(r"curl\b.*\|\s*(?:sh|bash)", re.IGNORECASE),
    "dot-env": re.compile(r"(?m)(^|/)\.env(?:\s|$)"),
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    message: str


def read_template(name: str) -> str:
    return (CLOUD_INIT_DIR / name).read_text(encoding="utf-8")


def indent_after_first(width: int, text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    prefix = " " * width
    return "\n".join([lines[0], *[prefix + line if line else "" for line in lines[1:]]])


def render_simple_template(text: str, values: dict[str, object]) -> str:
    rendered = text
    for key, value in values.items():
        rendered = rendered.replace("${" + key + "}", str(value))
    return rendered.replace("$${", "${")


def render_child_templates() -> dict[str, str]:
    common = {
        "nginx_image_ref": NGINX_IMAGE_REF,
        "application_container_port": 8080,
        "application_health_path": "/health",
        "api_image_ref": API_IMAGE_REF,
        "web_image_ref": WEB_IMAGE_REF,
        "application_host_port": 8080,
        "application_root_dir": "/opt/edudocs",
        "application_start_timeout_seconds": 600,
    }
    return {
        "compose": render_simple_template(
            read_template("docker-compose.prod.yaml.tftpl"), common
        ),
        "nginx": render_simple_template(read_template("nginx.conf.tftpl"), common),
        "runtime_env": render_simple_template(read_template("runtime.env.tftpl"), common),
        "systemd": render_simple_template(
            read_template("edudocs-compose.service.tftpl"), common
        ),
    }


def render_cloud_init(children: dict[str, str]) -> str:
    text = read_template("app-server.yaml.tftpl")
    text = text.replace("${indent(6, compose_content)}", indent_after_first(6, children["compose"]))
    text = text.replace("${indent(6, nginx_content)}", indent_after_first(6, children["nginx"]))
    text = text.replace(
        "${indent(6, runtime_env_content)}",
        indent_after_first(6, children["runtime_env"]),
    )
    text = text.replace("${indent(6, systemd_content)}", indent_after_first(6, children["systemd"]))
    return render_simple_template(
        text,
        {
            "project_name": "edudocs-ai-production",
            "admin_cidr": "203.0.113.10/32",
            "public_subnet_cidr": "10.20.10.0/24",
            "application_root_dir": "/opt/edudocs",
            "application_host_port": 8080,
            "application_health_path": "/health",
            "application_start_timeout_seconds": 600,
        },
    )


def find_required_files() -> list[Finding]:
    findings: list[Finding] = []
    for name in sorted(REQUIRED_FILES):
        if not (CLOUD_INIT_DIR / name).is_file():
            findings.append(
                Finding(
                    f"infrastructure/cloud-init/{name}",
                    "missing-file",
                    "Template obrigatorio de bootstrap ausente.",
                )
            )
    return findings


def find_forbidden_content() -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(CLOUD_INIT_DIR.glob("*.tftpl")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for kind, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                findings.append(
                    Finding(rel, kind, "Template contem conteudo proibido.")
                )
    return findings


def inspect_compose_config(compose_json: dict[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    services = compose_json.get("services")
    if not isinstance(services, dict):
        return [
            Finding(
                "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                "compose-services",
                "Compose renderizado nao contem services.",
            )
        ]

    expected = {"api", "web", "nginx"}
    if set(services) != expected:
        findings.append(
            Finding(
                "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                "compose-service-set",
                "Compose deve conter exatamente api, web e nginx.",
            )
        )

    for name in ("api", "web"):
        service = services.get(name, {})
        if not isinstance(service, dict):
            continue
        image = str(service.get("image", ""))
        expected_prefix = f"ghcr.io/brodyandre/edudocs-ai-{name}@sha256:"
        if not image.startswith(expected_prefix):
            findings.append(
                Finding(
                    "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                    f"{name}-image-ref",
                    f"{name} deve usar imagem GHCR por digest.",
                )
            )
        if service.get("ports"):
            findings.append(
                Finding(
                    "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                    f"{name}-host-port",
                    "API e Web nao podem publicar portas no host.",
                )
            )
        if service.get("read_only") is not True:
            findings.append(
                Finding(
                    "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                    f"{name}-read-only",
                    "Servicos da aplicacao devem rodar com read_only.",
                )
            )

    nginx = services.get("nginx", {})
    if isinstance(nginx, dict):
        if str(nginx.get("image", "")) != NGINX_IMAGE_REF:
            findings.append(
                Finding(
                    "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                    "nginx-image-ref",
                    "Nginx deve usar tag fixa permitida.",
                )
            )
        ports = json.dumps(nginx.get("ports", []), sort_keys=True)
        if "8080" not in ports or "3000" in ports or "8000" in ports:
            findings.append(
                Finding(
                    "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                    "nginx-port",
                    "Somente Nginx deve publicar a porta 8080.",
                )
            )
    return findings


def validate_compose(children: dict[str, str]) -> list[Finding]:
    if shutil.which("docker") is None:
        return [
            Finding(
                "docker",
                "docker-missing",
                "Docker e necessario para validar docker compose config.",
            )
        ]
    with tempfile.TemporaryDirectory(prefix="edudocs-bootstrap-") as tmp:
        tmp_path = Path(tmp)
        compose = tmp_path / "docker-compose.yml"
        env = tmp_path / "runtime.env"
        compose.write_text(children["compose"], encoding="utf-8")
        env.write_text(children["runtime_env"], encoding="utf-8")
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env),
                "-f",
                str(compose),
                "config",
                "--format",
                "json",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    if result.returncode != 0:
        return [
            Finding(
                "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
                "compose-config",
                result.stderr.strip() or "docker compose config falhou.",
            )
        ]
    return inspect_compose_config(json.loads(result.stdout))


def validate_text_contracts(children: dict[str, str], cloud_init: str) -> list[Finding]:
    checks = {
        "cloud-init-systemd": "systemctl enable edudocs-compose.service" in cloud_init
        and "systemctl start edudocs-compose.service" in cloud_init,
        "cloud-init-health": "http://127.0.0.1:8080/health" in cloud_init,
        "cloud-init-app-marker": "/var/lib/edudocs/application-ready" in cloud_init,
        "cloud-init-complete-marker": "/var/lib/edudocs/cloud-init-complete" in cloud_init,
        "runtime-fake-llm": "EDUDOCS_LLM_PROVIDER=fake" in children["runtime_env"],
        "runtime-fake-embedding": "EDUDOCS_EMBEDDING_PROVIDER=fake"
        in children["runtime_env"],
        "runtime-images": API_IMAGE_REF in children["runtime_env"]
        and WEB_IMAGE_REF in children["runtime_env"],
        "nginx-listen-8080": re.search(r"listen\s+8080;", children["nginx"])
        is not None,
        "nginx-health": "location = /health" in children["nginx"],
        "nginx-ready": "location = /ready" in children["nginx"],
        "nginx-pid-tmp": "pid /tmp/nginx.pid" in children["nginx"],
        "nginx-client-temp-tmp": "client_body_temp_path /tmp/client_temp"
        in children["nginx"],
        "nginx-proxy-temp-tmp": "proxy_temp_path /tmp/proxy_temp"
        in children["nginx"],
        "nginx-api-preserve-prefix": "proxy_pass http://api_upstream;" in children["nginx"],
        "systemd-pull": "docker compose" in children["systemd"]
        and " pull" in children["systemd"],
        "systemd-up": " up --detach --remove-orphans" in children["systemd"],
    }
    findings: list[Finding] = []
    for kind, passed in checks.items():
        if not passed:
            findings.append(
                Finding(
                    "infrastructure/cloud-init",
                    kind,
                    "Contrato obrigatorio do bootstrap nao foi encontrado.",
                )
            )
    return findings


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(find_required_files())
    findings.extend(find_forbidden_content())
    if findings:
        return findings
    children = render_child_templates()
    cloud_init = render_cloud_init(children)
    findings.extend(validate_text_contracts(children, cloud_init))
    findings.extend(validate_compose(children))
    return findings


def main() -> int:
    findings = collect_findings()
    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.kind}: {finding.message}")
        return 1
    print("OK: bootstrap declarativo da aplicacao validado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
