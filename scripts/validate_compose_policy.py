from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    guidance: str


def validate_compose(compose: dict[str, Any], nginx_config: str) -> list[Finding]:
    services = compose.get("services", {})
    findings: list[Finding] = []

    expected_services = {"api", "web", "nginx"}
    if set(services) != expected_services:
        findings.append(Finding("services", "unexpected-services", "Mantenha apenas api, web e nginx no Compose local."))

    for service_name in ("api", "web", "nginx"):
        service = services.get(service_name, {})
        if "healthcheck" not in service:
            findings.append(Finding(f"services.{service_name}", "missing-healthcheck", "Defina healthcheck."))
        if service.get("read_only") is not True:
            findings.append(Finding(f"services.{service_name}", "not-read-only", "Use read_only: true."))
        if "ALL" not in service.get("cap_drop", []):
            findings.append(Finding(f"services.{service_name}", "missing-cap-drop", "Use cap_drop: [ALL]."))
        if "no-new-privileges:true" not in service.get("security_opt", []):
            findings.append(
                Finding(f"services.{service_name}", "missing-no-new-privileges", "Use no-new-privileges:true.")
            )

    for service_name in ("api", "web"):
        if services.get(service_name, {}).get("ports"):
            findings.append(Finding(f"services.{service_name}.ports", "internal-port-exposed", "Exponha apenas o Nginx."))

    nginx_ports = services.get("nginx", {}).get("ports", [])
    if len(nginx_ports) != 1 or str(nginx_ports[0].get("published")) != "8080" or nginx_ports[0].get("target") != 8080:
        findings.append(Finding("services.nginx.ports", "unexpected-public-port", "Publique somente 8080:8080."))

    api_env = services.get("api", {}).get("environment", {})
    if api_env.get("EDUDOCS_LLM_PROVIDER") != "fake" or api_env.get("EDUDOCS_EMBEDDING_PROVIDER") != "fake":
        findings.append(Finding("services.api.environment", "non-fake-provider", "Use providers fake no Compose local."))

    if "/api/api" in nginx_config:
        findings.append(Finding("infrastructure/nginx/nginx.conf", "double-api-prefix", "Nao crie rotas /api/api."))
    for route in ("location /api/", "location = /health", "location = /ready"):
        if route not in nginx_config:
            findings.append(Finding("infrastructure/nginx/nginx.conf", "missing-route", f"Configure {route}."))

    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.path}: {finding.kind}: {finding.guidance}")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("uso: validate_compose_policy.py COMPOSE_CONFIG_JSON NGINX_CONF", file=sys.stderr)
        return 2
    compose = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    nginx_config = Path(argv[2]).read_text(encoding="utf-8")
    findings = validate_compose(compose, nginx_config)
    if findings:
        print_findings(findings)
        return 1
    print("OK: politica Docker Compose/Nginx validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
