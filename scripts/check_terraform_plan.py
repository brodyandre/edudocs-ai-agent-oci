#!/usr/bin/env python3
"""Audita JSONs de terraform plan real sem executar apply."""

from __future__ import annotations

import argparse
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
LOAD_BALANCER_BACKEND_SET_NAME = "edudocs-ai-prod-backend-set"
LOAD_BALANCER_BACKEND_SET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
RECOVERY_ALLOWED_CREATE_ADDRESSES = {
    "module.load_balancer.oci_load_balancer_backend_set.app",
    "module.load_balancer.oci_load_balancer_backend.app",
    "module.load_balancer.oci_load_balancer_listener.http",
}
RECOVERY_ALLOWED_CREATE_TYPES = {
    "oci_load_balancer_backend_set",
    "oci_load_balancer_backend",
    "oci_load_balancer_listener",
}
NETWORK_RESOURCE_TYPES = {
    "oci_core_internet_gateway",
    "oci_core_network_security_group",
    "oci_core_network_security_group_security_rule",
    "oci_core_route_table",
    "oci_core_subnet",
    "oci_core_vcn",
}
EXPECTED_STATE_DATA_TYPES = {
    "oci_core_images",
    "oci_identity_availability_domains",
}
OCI_COMPARTMENT_PREFIX = "ocid1." + "compartment.oc1."

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


def load_tfvars(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    text = path.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for key in ("tenancy_ocid", "compartment_ocid"):
        match = re.search(rf'(?m)^\s*{key}\s*=\s*"([^"]+)"', text)
        if match:
            values[key] = match.group(1)
    return values


def load_state_addresses(path: Path | None) -> list[str]:
    if path is None:
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def state_address_type(address: str) -> tuple[str, bool] | None:
    parts = address.split(".")
    if len(parts) < 2:
        return None
    if parts[0] == "data" and len(parts) >= 3:
        return parts[-2], True
    return parts[-2], False


def valid_load_balancer_backend_set_name_format(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 32
        and " " not in value
        and bool(LOAD_BALANCER_BACKEND_SET_NAME_PATTERN.fullmatch(value))
    )


def valid_load_balancer_backend_set_name(value: Any) -> bool:
    return (
        value == LOAD_BALANCER_BACKEND_SET_NAME
        and valid_load_balancer_backend_set_name_format(value)
    )


def resource_changes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    changes = plan.get("resource_changes", [])
    return [item for item in changes if isinstance(item, dict)]


def collect_resource_findings(
    changes: list[dict[str, Any]], tfvars: dict[str, str] | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    tfvars = tfvars or {}
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

        findings.extend(validate_resource_values(address, resource_type, after, tfvars))
    return findings


def validate_resource_values(
    address: str,
    resource_type: str,
    values: dict[str, Any],
    tfvars: dict[str, str] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    tfvars = tfvars or {}
    tenancy_ocid = tfvars.get("tenancy_ocid")
    compartment_ocid = tfvars.get("compartment_ocid")
    compartment_id = values.get("compartment_id")

    if resource_type in {
        "oci_core_instance",
        "oci_core_internet_gateway",
        "oci_core_network_security_group",
        "oci_core_route_table",
        "oci_core_subnet",
        "oci_core_vcn",
        "oci_load_balancer_load_balancer",
        "oci_objectstorage_bucket",
    }:
        if tenancy_ocid and compartment_id == tenancy_ocid:
            findings.append(
                Finding(
                    address,
                    "workload-root-compartment",
                    "Recurso de workload nao pode usar tenancy/root compartment.",
                )
            )
        if compartment_ocid and compartment_id and compartment_id != compartment_ocid:
            findings.append(
                Finding(
                    address,
                    "workload-compartment-mismatch",
                    "Recurso de workload deve usar o compartment filho do tfvars.",
                )
            )

    if resource_type == "oci_core_instance":
        if values.get("shape") != "VM.Standard.E4.Flex":
            findings.append(
                Finding(address, "compute-shape", "Compute deve usar VM.Standard.E4.Flex.")
            )
        shape_config = values.get("shape_config") or []
        if not shape_config:
            findings.append(
                Finding(address, "compute-shape-config", "shape_config e obrigatorio.")
            )
        else:
            config = shape_config[0]
            if as_int(config.get("ocpus")) != 1:
                findings.append(
                    Finding(address, "compute-ocpus", "OCPUs devem ser exatamente 1.")
                )
            if as_int(config.get("memory_in_gbs")) != 8:
                findings.append(
                    Finding(address, "compute-memory", "Memoria esperada: 8 GB.")
                )
        source_details = values.get("source_details") or []
        if not source_details:
            findings.append(
                Finding(address, "compute-source-details", "source_details e obrigatorio.")
            )
        else:
            details = source_details[0]
            if as_int(details.get("boot_volume_size_in_gbs")) != 50:
                findings.append(
                    Finding(
                        address,
                        "compute-boot-volume",
                        "Boot volume esperado: 50 GB.",
                    )
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
        backend_set_name = values.get("default_backend_set_name")
        if backend_set_name is not None and not valid_load_balancer_backend_set_name(
            backend_set_name
        ):
            findings.append(
                Finding(
                    address,
                    "lb-listener-backend-set",
                    "Listener deve apontar para edudocs-ai-prod-backend-set.",
                )
            )
    elif resource_type == "oci_load_balancer_backend":
        backend_set_name = values.get("backendset_name")
        if backend_set_name is not None and not valid_load_balancer_backend_set_name(
            backend_set_name
        ):
            findings.append(
                Finding(
                    address,
                    "lb-backend-set-name",
                    "Backend deve apontar para edudocs-ai-prod-backend-set.",
                )
            )
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
        if not valid_load_balancer_backend_set_name(values.get("name")):
            findings.append(
                Finding(
                    address,
                    "lb-backend-set-name",
                    "Backend set deve se chamar edudocs-ai-prod-backend-set.",
                )
            )
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


def collect_recovery_findings(
    plan: dict[str, Any],
    tfvars: dict[str, str] | None = None,
    state_addresses: list[str] | None = None,
) -> list[Finding]:
    state_addresses = state_addresses or []
    findings: list[Finding] = []
    changes = resource_changes(plan)

    if not state_addresses:
        findings.append(
            Finding("state", "state-empty", "Recovery exige state principal nao vazio.")
        )

    for address in state_addresses:
        parsed = state_address_type(address)
        if parsed is None:
            findings.append(
                Finding(address, "state-address-invalid", "Address de state invalido.")
            )
            continue
        resource_type, is_data = parsed
        allowed = (
            resource_type in EXPECTED_STATE_DATA_TYPES
            if is_data
            else resource_type in ALLOWED_RESOURCE_TYPES
        )
        if not allowed:
            findings.append(
                Finding(
                    address,
                    "state-type-unexpected",
                    f"Tipo inesperado no state: {resource_type}.",
                )
            )

    state_set = set(state_addresses)
    missing_expected = RECOVERY_ALLOWED_CREATE_ADDRESSES - state_set
    create_addresses: set[str] = set()

    for item in changes:
        if item.get("mode") != "managed":
            continue
        address = item.get("address", "<unknown>")
        resource_type = item.get("type", "")
        change = item.get("change", {})
        actions = change.get("actions", [])
        after = change.get("after") or {}

        if resource_type not in ALLOWED_RESOURCE_TYPES:
            findings.append(
                Finding(
                    address,
                    "resource-not-allowed",
                    f"Tipo fora da allowlist: {resource_type}.",
                )
            )
        if any(action in actions for action in ("update", "delete", "replace")):
            findings.append(
                Finding(
                    address,
                    "recovery-mutates-existing-resource",
                    "Recovery nao pode alterar, substituir ou destruir recursos.",
                )
            )
        if actions == ["create"]:
            create_addresses.add(address)
            if (
                resource_type not in RECOVERY_ALLOWED_CREATE_TYPES
                or address not in RECOVERY_ALLOWED_CREATE_ADDRESSES
            ):
                findings.append(
                    Finding(
                        address,
                        "recovery-create-not-allowed",
                        "Recovery so pode criar backend set, backend e listener faltantes.",
                    )
                )
            if address not in missing_expected:
                findings.append(
                    Finding(
                        address,
                        "recovery-create-not-missing",
                        "Recovery nao pode criar recurso ja presente no state.",
                    )
                )
        elif actions not in (["no-op"], ["read"], []):
            findings.append(
                Finding(
                    address,
                    "recovery-unexpected-action",
                    f"Acoes inesperadas no recovery plan: {','.join(actions)}.",
                )
            )
        if (
            actions == ["create"]
            or resource_type in RECOVERY_ALLOWED_CREATE_TYPES
        ):
            findings.extend(validate_resource_values(address, resource_type, after, tfvars))
        if actions == ["create"] and resource_type == "oci_core_instance":
            findings.append(
                Finding(address, "recovery-compute-create", "Recovery nao pode criar Compute.")
            )
        if actions == ["create"] and resource_type == "oci_load_balancer_load_balancer":
            findings.append(
                Finding(
                    address,
                    "recovery-lb-create",
                    "Recovery nao pode criar o Load Balancer principal.",
                )
            )
        if actions == ["create"] and resource_type in NETWORK_RESOURCE_TYPES:
            findings.append(
                Finding(address, "recovery-network-create", "Recovery nao pode criar rede.")
            )

    if create_addresses != missing_expected:
        findings.append(
            Finding(
                "plan",
                "recovery-create-set",
                "Creates do recovery devem corresponder exatamente aos recursos faltantes.",
            )
        )

    findings.extend(collect_text_findings(plan))
    findings.extend(collect_configuration_findings(plan, tfvars))
    return findings


def collect_configuration_findings(
    plan: dict[str, Any], tfvars: dict[str, str] | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    tfvars = tfvars or {}
    root = plan.get("configuration", {}).get("root_module", {})
    text = json.dumps(root, sort_keys=True, ensure_ascii=False)
    if tfvars:
        tenancy = tfvars.get("tenancy_ocid", "")
        compartment = tfvars.get("compartment_ocid", "")
        if tenancy and compartment and tenancy == compartment:
            findings.append(
                Finding(
                    "tfvars",
                    "tfvars-root-compartment",
                    "compartment_ocid nao pode ser igual a tenancy_ocid.",
                )
            )
        if compartment and not compartment.startswith(OCI_COMPARTMENT_PREFIX):
            findings.append(
                Finding(
                    "tfvars",
                    "tfvars-compartment-ocid",
                    "compartment_ocid deve ser OCID de compartment.",
                )
            )
    for forbidden in (
        "allow_root_compartment",
        "use_root_compartment",
        "skip_compartment_validation",
    ):
        if forbidden in text:
            findings.append(
                Finding("configuration", "root-escape-hatch", "Escape hatch de root proibido.")
            )
    if re.search(r"var\.tenancy_ocid", text) and re.search(
        r"oci_(?:core|load_balancer|objectstorage)", text
    ):
        # Data sources/provider can use tenancy. Managed workload resources are checked
        # through resource values above; this catches accidental direct expressions.
        if "compartment_ocid" not in text:
            findings.append(
                Finding(
                    "configuration",
                    "configuration-uses-tenancy",
                    "Configuracao de workload nao deve depender de tenancy_ocid como compartment.",
                )
            )
    return findings


def collect_findings(
    plan: dict[str, Any], tfvars: dict[str, str] | None = None
) -> list[Finding]:
    changes = resource_changes(plan)
    findings: list[Finding] = []
    findings.extend(collect_resource_findings(changes, tfvars))
    findings.extend(collect_text_findings(plan))
    findings.extend(collect_configuration_findings(plan, tfvars))
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_json")
    parser.add_argument("--tfvars")
    parser.add_argument(
        "--mode",
        choices=("initial", "partial-apply-recovery"),
        default="initial",
    )
    parser.add_argument("--state-addresses")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        plan = load_plan(Path(args.plan_json))
        tfvars = load_tfvars(Path(args.tfvars) if args.tfvars else None)
        state_addresses = load_state_addresses(
            Path(args.state_addresses) if args.state_addresses else None
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"plan: invalid-json: {exc}", file=sys.stderr)
        return 1
    if args.mode == "partial-apply-recovery":
        findings = collect_recovery_findings(plan, tfvars, state_addresses)
    else:
        findings = collect_findings(plan, tfvars)
    if findings:
        for finding in findings:
            print(f"{finding.address}: {finding.kind}: {finding.message}")
        return 1
    if args.mode == "partial-apply-recovery":
        print("OK: terraform recovery plan auditado sem acoes proibidas.")
    else:
        print("OK: terraform plan real auditado sem acoes proibidas.")
    for resource_type, count in summarize(resource_changes(plan)).items():
        print(f"- {resource_type}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
