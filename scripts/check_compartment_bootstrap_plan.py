#!/usr/bin/env python3
"""Audita o plan JSON do stack bootstrap do compartment OCI."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_NAME = "edudocs-ai-prod"
EXPECTED_DESCRIPTION = "Recursos de producao do projeto EduDocs AI."
REQUIRED_TAGS = {
    "Project": "EduDocs-AI",
    "Environment": "production",
    "ManagedBy": "Terraform",
    "Purpose": "Application-Workload",
    "CostProfile": "Always-Free-Target",
}

SECRET_PATTERNS = {
    "github-token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    "github-pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "fingerprint": re.compile(r"\bfingerprint\b", re.IGNORECASE),
}


@dataclass(frozen=True)
class Finding:
    address: str
    kind: str
    message: str


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("plan JSON precisa ser objeto")
    return data


def load_tfvars(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for key in ("tenancy_ocid", "region", "config_file_profile", "compartment_name"):
        match = re.search(rf'(?m)^\s*{key}\s*=\s*"([^"]+)"', text)
        if match:
            values[key] = match.group(1)
    return values


def resource_changes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in plan.get("resource_changes", []) if isinstance(item, dict)]


def configuration_resources(plan: dict[str, Any]) -> list[dict[str, Any]]:
    root = plan.get("configuration", {}).get("root_module", {})
    resources = root.get("resources", [])
    return [item for item in resources if isinstance(item, dict)]


def collect_findings(plan: dict[str, Any], tfvars: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    changes = resource_changes(plan)
    managed = [item for item in changes if item.get("mode") == "managed"]

    if len(managed) != 1:
        findings.append(
            Finding("plan", "resource-count", "Plan deve conter exatamente um recurso gerenciado.")
        )
    if managed:
        item = managed[0]
        address = item.get("address", "<unknown>")
        change = item.get("change", {})
        actions = change.get("actions", [])
        after = change.get("after") or {}
        if item.get("type") != "oci_identity_compartment":
            findings.append(
                Finding(address, "resource-type", "Tipo unico deve ser oci_identity_compartment.")
            )
        if actions != ["create"]:
            findings.append(
                Finding(address, "action", "Plan deve ser exatamente um create.")
            )
        if any(action in actions for action in ("update", "delete", "replace")):
            findings.append(
                Finding(address, "mutating-action", "Plan nao pode update/delete/replace.")
            )
        if after.get("name") != EXPECTED_NAME:
            findings.append(Finding(address, "name", "Nome deve ser edudocs-ai-prod."))
        if after.get("description") != EXPECTED_DESCRIPTION:
            findings.append(Finding(address, "description", "Descricao inesperada."))
        if after.get("compartment_id") != tfvars.get("tenancy_ocid"):
            findings.append(Finding(address, "parent", "Parent deve ser tenancy_ocid do tfvars."))
        if after.get("enable_delete") is not False:
            findings.append(Finding(address, "enable-delete", "enable_delete deve ser false."))
        tags = after.get("freeform_tags") or {}
        for key, value in REQUIRED_TAGS.items():
            if tags.get(key) != value:
                findings.append(Finding(address, "required-tag", "Tags obrigatorias ausentes."))
                break

    findings.extend(validate_configuration(plan))
    findings.extend(validate_text(plan))
    return findings


def validate_configuration(plan: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    resources = configuration_resources(plan)
    if len(resources) != 1:
        findings.append(
            Finding("configuration", "resource-count", "Configuration deve declarar um recurso.")
        )
    for resource in resources:
        address = resource.get("address", "<unknown>")
        if resource.get("type") != "oci_identity_compartment":
            findings.append(
                Finding(address, "resource-type", "Configuration contem recurso proibido.")
            )
        expressions = resource.get("expressions", {})
        if "compartment_id" not in expressions:
            findings.append(
                Finding(address, "missing-parent-expression", "Parent precisa vir de var.tenancy_ocid.")
            )
    return findings


def validate_text(plan: dict[str, Any]) -> list[Finding]:
    text = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    findings: list[Finding] = []
    for kind, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            findings.append(Finding("plan", kind, "Plan contem conteudo sensivel."))
    for forbidden in (
        "oci_core_vcn",
        "oci_core_instance",
        "oci_load_balancer_load_balancer",
        "oci_identity_policy",
        "oci_limits_quota",
        "oci_objectstorage_bucket",
    ):
        if forbidden in text:
            findings.append(
                Finding("plan", "forbidden-resource", f"Plan contem {forbidden}.")
            )
    return findings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--tfvars", required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        plan = load_json(Path(args.plan_json))
        tfvars = load_tfvars(Path(args.tfvars))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"plan: invalid-input: {type(exc).__name__}", file=sys.stderr)
        return 1
    findings = collect_findings(plan, tfvars)
    if findings:
        for finding in findings:
            print(f"{finding.address}: {finding.kind}: {finding.message}")
        return 1
    print("OK: plan do bootstrap do compartment aprovado.")
    print("- create: 1")
    print("- update: 0")
    print("- replace: 0")
    print("- delete: 0")
    print("- type: oci_identity_compartment")
    print("- name: edudocs-ai-prod")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
