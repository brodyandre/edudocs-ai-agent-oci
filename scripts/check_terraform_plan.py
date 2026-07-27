#!/usr/bin/env python3
"""Audita o JSON do primeiro terraform plan real sem executar apply."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_RESOURCE_TYPES = {
    "oci_core_instance",
    "oci_core_internet_gateway",
    "oci_core_network_security_group",
    "oci_core_network_security_group_security_rule",
    "oci_core_route_table",
    "oci_core_subnet",
    "oci_core_vcn",
    "oci_load_balancer_backend",
    "oci_load_balancer_backend_set",
    "oci_load_balancer_listener",
    "oci_load_balancer_load_balancer",
    "oci_objectstorage_bucket",
}

FORBIDDEN_TEXT_PATTERNS = {
    "latest-reference": re.compile(r"(?<![A-Za-z0-9_-])latest(?![A-Za-z0-9_-])", re.I),
    "docker-login": re.compile(r"\bdocker\s+login\b", re.I),
    "git-clone": re.compile(r"\bgit\s+clone\b", re.I),
    "groq-secret": re.compile(r"\bGROQ_API_KEY\b", re.I),
    "github-token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    "github-pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
}


@dataclass(frozen=True)
class Finding:
    address: str
    kind: str
    message: str


def as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def load_plan(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("plan JSON precisa ser um objeto")
    return data


def resource_changes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    changes = plan.get("resource_changes", [])
    return [item for item in changes if isinstance(item, dict)]


def collect_resource_findings(changes: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    for item in changes:
        address = item.get("address", "<unknown>")
        resource_type = item.get("type", "")
        mode = item.get("mode", "managed")
        change = item.get("change", {})
        actions = change.get("actions", [])
        after = change.get("after") or {}

        if mode != "managed":
            continue
        if resource_type not in ALLOWED_RESOURCE_TYPES:
            findings.append(
                Finding(
                    address,
                    "resource-not-allowed",
                    f"Tipo fora da allowlist: {resource_type}.",
                )
            )
        if any(action in actions for action in ("delete", "replace", "update")):
            findings.append(
                Finding(
                    address,
                    "mutating-existing-resource",
                    "Primeiro plan esperado deve criar recursos, sem update/delete/replace.",
                )
            )
        if actions and actions != ["create"] and actions != ["no-op"]:
            findings.append(
                Finding(
                    address,
                    "unexpected-action",
                    f"Acoes inesperadas no plan: {','.join(actions)}.",
                )
            )

        findings.extend(validate_resource_values(address, resource_type, after))
    return findings


def validate_resource_values(
    address: str, resource_type: str, values: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    if resource_type == "oci_core_instance":
        if values.get("shape") != "VM.Standard.A1.Flex":
            findings.append(
                Finding(address, "compute-shape", "Compute deve usar VM.Standard.A1.Flex.")
            )
        shape_config = values.get("shape_config") or []
        if shape_config:
            config = shape_config[0]
            if as_int(config.get("ocpus")) not in {1, 2}:
                findings.append(
                    Finding(address, "compute-ocpus", "OCPUs devem ficar ate 2.")
                )
            if as_int(config.get("memory_in_gbs")) != 12:
                findings.append(
                    Finding(address, "compute-memory", "Memoria esperada: 12 GB.")
                )
    elif resource_type == "oci_load_balancer_load_balancer":
        if values.get("shape") != "flexible" or values.get("is_private") is not False:
            findings.append(
                Finding(address, "lb-shape", "Load Balancer deve ser flexible publico.")
            )
        details = values.get("shape_details") or []
        if details:
            item = details[0]
            if (
                as_int(item.get("minimum_bandwidth_in_mbps")) != 10
                or as_int(item.get("maximum_bandwidth_in_mbps")) != 10
            ):
                findings.append(
                    Finding(address, "lb-bandwidth", "Load Balancer deve ser 10/10 Mbps.")
                )
    elif resource_type == "oci_load_balancer_listener":
        if values.get("protocol") != "HTTP" or as_int(values.get("port")) != 80:
            findings.append(
                Finding(address, "lb-listener", "Listener deve ser HTTP na porta 80.")
            )
    elif resource_type == "oci_load_balancer_backend":
        if as_int(values.get("port")) != 8080:
            findings.append(
                Finding(address, "lb-backend-port", "Backend deve usar porta 8080.")
            )
        ip = values.get("ip_address")
        if isinstance(ip, str) and ip and not re.match(
            r"^(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)", ip
        ):
            findings.append(
                Finding(address, "lb-backend-ip", "Backend deve usar IP privado.")
            )
    elif resource_type == "oci_load_balancer_backend_set":
        health = values.get("health_checker") or []
        if health:
            item = health[0]
            if (
                item.get("protocol") != "HTTP"
                or as_int(item.get("port")) != 8080
                or item.get("url_path") != "/health"
                or as_int(item.get("return_code")) != 200
            ):
                findings.append(
                    Finding(address, "lb-health", "Health checker deve ser HTTP 8080 /health 200.")
                )
    elif resource_type == "oci_core_network_security_group_security_rule":
        source = values.get("source")
        direction = values.get("direction")
        tcp_options = values.get("tcp_options") or []
        ports: set[int] = set()
        for option in tcp_options:
            ranges = option.get("destination_port_range") or []
            for port_range in ranges:
                for key in ("min", "max"):
                    port = as_int(port_range.get(key))
                    if port is not None:
                        ports.add(port)
        if direction == "INGRESS" and source == "0.0.0.0/0" and 22 in ports:
            findings.append(
                Finding(address, "ssh-public", "SSH nao pode ficar publico.")
            )
        if direction == "INGRESS" and source == "0.0.0.0/0" and ports & {3000, 8000, 8080}:
            findings.append(
                Finding(
                    address,
                    "public-internal-port",
                    "Portas 3000/8000/8080 nao podem ficar publicas.",
                )
            )
    return findings


def collect_text_findings(plan: dict[str, Any]) -> list[Finding]:
    text = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    findings: list[Finding] = []
    for kind, pattern in FORBIDDEN_TEXT_PATTERNS.items():
        if pattern.search(text):
            findings.append(
                Finding("plan", kind, "Plan contem texto proibido ou sensivel.")
            )
    return findings


def summarize(changes: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in changes:
        if item.get("mode") != "managed":
            continue
        resource_type = item.get("type", "unknown")
        actions = item.get("change", {}).get("actions", [])
        if actions == ["create"]:
            summary[resource_type] = summary.get(resource_type, 0) + 1
    return dict(sorted(summary.items()))


def collect_findings(plan: dict[str, Any]) -> list[Finding]:
    changes = resource_changes(plan)
    findings: list[Finding] = []
    findings.extend(collect_resource_findings(changes))
    findings.extend(collect_text_findings(plan))
    if not any(item.get("type") == "oci_load_balancer_load_balancer" for item in changes):
        findings.append(
            Finding(
                "plan",
                "missing-load-balancer",
                "Plan deve conter um OCI Flexible Load Balancer.",
            )
        )
    if sum(1 for item in changes if item.get("type") == "oci_load_balancer_load_balancer") != 1:
        findings.append(
            Finding(
                "plan",
                "load-balancer-count",
                "Plan deve conter exatamente um Load Balancer.",
            )
        )
    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("uso: check_terraform_plan.py PLAN_JSON", file=sys.stderr)
        return 2
    try:
        plan = load_plan(Path(argv[0]))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"plan: invalid-json: {exc}", file=sys.stderr)
        return 1
    findings = collect_findings(plan)
    if findings:
        for finding in findings:
            print(f"{finding.address}: {finding.kind}: {finding.message}")
        return 1
    print("OK: terraform plan real auditado sem acoes proibidas.")
    for resource_type, count in summarize(resource_changes(plan)).items():
        print(f"- {resource_type}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
