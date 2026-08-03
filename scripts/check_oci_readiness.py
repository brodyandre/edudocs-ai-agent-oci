#!/usr/bin/env python3
"""Audita pre-requisitos locais e leitura OCI antes do primeiro plan real."""

from __future__ import annotations

import argparse
import configparser
import ipaddress
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_REGION = "sa-saopaulo-1"
DEFAULT_SSH_PUBLIC_KEY = Path.home() / ".ssh" / "edudocs_oci_ed25519.pub"
OCI_COMPARTMENT_PREFIX = "ocid1." + "compartment.oc1."


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    message: str


def mask_ocid(value: str) -> str:
    if len(value) <= 24:
        return value[:8] + "..." if value else ""
    return f"{value[:18]}...{value[-6:]}"


def mask_cidr(value: str) -> str:
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        return "MASCARADO"
    if network.version != 4:
        return "MASCARADO"
    parts = str(network.network_address).split(".")
    return f"{parts[0]}.{parts[1]}.x.x/{network.prefixlen}"


def file_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def validate_admin_cidr(value: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        return [
            Finding(
                "EDUDOCS_ADMIN_CIDR",
                "invalid-admin-cidr",
                "EDUDOCS_ADMIN_CIDR deve ser IPv4 publico em /32.",
            )
        ]
    if network.version != 4 or network.prefixlen != 32:
        findings.append(
            Finding(
                "EDUDOCS_ADMIN_CIDR",
                "invalid-admin-cidr",
                "EDUDOCS_ADMIN_CIDR deve ser IPv4 publico em /32.",
            )
        )
    if network.is_private or network.is_loopback or network.is_multicast:
        findings.append(
            Finding(
                "EDUDOCS_ADMIN_CIDR",
                "non-public-admin-cidr",
                "EDUDOCS_ADMIN_CIDR deve ser publico, nao privado/local.",
            )
        )
    return findings


def load_profile(profile: str) -> tuple[configparser.SectionProxy | None, list[Finding]]:
    config_path = Path.home() / ".oci" / "config"
    findings: list[Finding] = []
    if file_mode(Path.home() / ".oci") != 0o700:
        findings.append(
            Finding("~/.oci", "oci-dir-permission", "~/.oci deve estar com permissao 700.")
        )
    if file_mode(config_path) != 0o600:
        findings.append(
            Finding(
                "~/.oci/config",
                "oci-config-permission",
                "~/.oci/config deve estar com permissao 600.",
            )
        )
    parser = configparser.ConfigParser()
    parser.read(config_path)
    if not parser.has_section(profile):
        findings.append(
            Finding("~/.oci/config", "missing-profile", f"Perfil {profile} ausente.")
        )
        return None, findings
    section = parser[profile]
    for key in ("user", "fingerprint", "tenancy", "region", "key_file"):
        if key not in section or not section[key].strip():
            findings.append(
                Finding("~/.oci/config", "missing-profile-key", f"Chave {key} ausente.")
            )
    key_file = Path(section.get("key_file", "")).expanduser()
    if file_mode(key_file) != 0o600:
        findings.append(
            Finding(
                "api_key",
                "api-key-permission",
                "Chave privada de API OCI deve existir e estar com permissao 600.",
            )
        )
    return section, findings


def oci_json(profile: str, args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        ["oci", *args, "--profile", profile, "--output", "json"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not completed.stdout.strip():
        return {"data": []}
    return json.loads(completed.stdout)


def validate_target_compartment(
    compartments: list[dict[str, Any]], tenancy: str, compartment_name: str
) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    summary: dict[str, Any] = {}
    matches = [item for item in compartments if item.get("name") == compartment_name]

    summary["target_compartment"] = compartment_name
    summary["target_compartment_matches"] = len(matches)

    if len(matches) != 1:
        findings.append(
            Finding(
                "oci:compartment",
                "target-compartment-count",
                f"Deve existir exatamente um compartment chamado {compartment_name}.",
            )
        )
        return findings, summary

    target = matches[0]
    lifecycle_state = target.get("lifecycle-state", "")
    target_ocid = target.get("id", "")
    parent_ocid = target.get("compartment-id", "")
    summary["target_compartment_state"] = lifecycle_state
    summary["target_compartment_ocid"] = mask_ocid(target_ocid)
    summary["target_compartment_parent"] = "tenancy" if parent_ocid == tenancy else "outro"

    if lifecycle_state != "ACTIVE":
        findings.append(
            Finding(
                "oci:compartment",
                "target-compartment-not-active",
                "Compartment alvo deve estar ACTIVE antes do plan do workload.",
            )
        )
    if target_ocid == tenancy or not target_ocid.startswith(OCI_COMPARTMENT_PREFIX):
        findings.append(
            Finding(
                "oci:compartment",
                "target-compartment-root",
                "Workload deve usar compartment filho dedicado, nunca root/tenancy.",
            )
        )
    if parent_ocid != tenancy:
        findings.append(
            Finding(
                "oci:compartment",
                "target-compartment-parent",
                "Compartment alvo deve ser filho direto da tenancy validada.",
            )
        )
    return findings, summary


def validate_empty_workload_resources(
    instances: list[dict[str, Any]], load_balancers: list[dict[str, Any]]
) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    summary: dict[str, Any] = {}

    active_compute_instances = [
        item
        for item in instances
        if item.get("lifecycle-state") not in {"TERMINATED", "TERMINATING"}
    ]
    active_e4_instances = [
        item
        for item in active_compute_instances
        if item.get("shape") == "VM.Standard.E4.Flex"
    ]
    active_a1_instances = [
        item
        for item in active_compute_instances
        if item.get("shape") == "VM.Standard.A1.Flex"
    ]
    existing_load_balancers = [
        item
        for item in load_balancers
        if item.get("lifecycle-state") not in {"DELETED", "DELETING"}
    ]

    summary["target_compute_shape"] = "VM.Standard.E4.Flex"
    summary["target_compute_ocpus"] = 1
    summary["target_compute_memory_gbs"] = 8
    summary["target_boot_volume_size_gbs"] = 50
    summary["payg_budget_required"] = True
    summary["capacity_report_required"] = True
    summary["existing_compute_instances"] = len(active_compute_instances)
    summary["existing_e4_flex_instances"] = len(active_e4_instances)
    summary["existing_a1_flex_instances"] = len(active_a1_instances)
    summary["existing_compute_shapes"] = sorted(
        {
            item.get("shape", "UNKNOWN")
            for item in active_compute_instances
            if item.get("shape")
        }
    )
    summary["existing_a1_flex_states"] = sorted(
        {
            item.get("lifecycle-state", "UNKNOWN")
            for item in active_a1_instances
            if item.get("lifecycle-state")
        }
    )
    summary["existing_load_balancers"] = len(existing_load_balancers)
    summary["existing_load_balancer_states"] = sorted(
        {
            item.get("lifecycle-state", "UNKNOWN")
            for item in existing_load_balancers
            if item.get("lifecycle-state")
        }
    )

    if active_compute_instances:
        findings.append(
            Finding(
                "oci:compute",
                "existing-compute-instance",
                "Compartment alvo ja possui instancia Compute nao terminada.",
            )
        )
    if active_a1_instances:
        findings.append(
            Finding(
                "oci:compute",
                "existing-a1-flex-instance",
                "Compartment alvo ja possui VM A1 Flex nao terminada; A1 nao e o perfil ativo desta entrega.",
            )
        )
    if existing_load_balancers:
        findings.append(
            Finding(
                "oci:load-balancer",
                "existing-load-balancer",
                "Compartment alvo ja possui Load Balancer nao removido.",
            )
        )
    return findings, summary


def collect_findings(
    profile: str, ssh_public_key: Path, compartment_name: str
) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    summary: dict[str, Any] = {"profile": profile}

    if not shutil_which("oci"):
        findings.append(Finding("oci", "oci-cli-missing", "OCI CLI nao encontrado."))
        return findings, summary

    admin_cidr = os.environ.get("EDUDOCS_ADMIN_CIDR", "").strip()
    findings.extend(validate_admin_cidr(admin_cidr))
    summary["admin_cidr"] = mask_cidr(admin_cidr)

    if not ssh_public_key.is_file():
        findings.append(
            Finding(
                str(ssh_public_key),
                "ssh-public-key-missing",
                "Chave publica SSH da VM ausente.",
            )
        )
    summary["ssh_public_key"] = str(ssh_public_key)

    section, profile_findings = load_profile(profile)
    findings.extend(profile_findings)
    if section is None:
        return findings, summary

    tenancy = section["tenancy"]
    region = section["region"]
    summary["region"] = region
    summary["tenancy"] = mask_ocid(tenancy)
    if region != EXPECTED_REGION:
        findings.append(
            Finding(
                "~/.oci/config",
                "unexpected-region",
                f"Regiao esperada: {EXPECTED_REGION}.",
            )
        )

    try:
        user = oci_json(profile, ["iam", "user", "get", "--user-id", section["user"]])[
            "data"
        ]
        summary["auth_user"] = user.get("name", "")
        tenancy_data = oci_json(
            profile, ["iam", "tenancy", "get", "--tenancy-id", tenancy]
        )["data"]
        summary["tenancy_name"] = tenancy_data.get("name", "")
        regions = oci_json(
            profile,
            ["iam", "region-subscription", "list", "--tenancy-id", tenancy, "--all"],
        )["data"]
        ready_regions = sorted(
            item.get("region-name", "")
            for item in regions
            if item.get("status") == "READY"
        )
        summary["ready_regions"] = ready_regions
        if EXPECTED_REGION not in ready_regions:
            findings.append(
                Finding(
                    "oci:region-subscription",
                    "region-not-ready",
                    f"{EXPECTED_REGION} deve estar READY.",
                )
            )
        ads = oci_json(
            profile, ["iam", "availability-domain", "list", "--compartment-id", tenancy]
        )["data"]
        summary["availability_domains"] = [item.get("name", "") for item in ads]
        if not ads:
            findings.append(
                Finding(
                    "oci:availability-domain",
                    "availability-domain-missing",
                    "Nenhum availability domain retornado.",
                )
            )
        compartments = oci_json(
            profile,
            [
                "iam",
                "compartment",
                "list",
                "--compartment-id",
                tenancy,
                "--compartment-id-in-subtree",
                "true",
                "--all",
            ],
        ).get("data", [])
        active_compartments = sorted(
            item.get("name", "")
            for item in compartments
            if item.get("lifecycle-state") == "ACTIVE"
        )
        summary["active_compartments"] = active_compartments
        compartment_findings, compartment_summary = validate_target_compartment(
            compartments, tenancy, compartment_name
        )
        findings.extend(compartment_findings)
        summary.update(compartment_summary)
        target_ocid = next(
            (
                item.get("id", "")
                for item in compartments
                if item.get("name") == compartment_name
                and item.get("lifecycle-state") == "ACTIVE"
                and item.get("id", "") != tenancy
            ),
            "",
        )
        if target_ocid:
            instances = oci_json(
                profile,
                [
                    "compute",
                    "instance",
                    "list",
                    "--compartment-id",
                    target_ocid,
                    "--all",
                ],
            ).get("data", [])
            load_balancers = oci_json(
                profile,
                [
                    "lb",
                    "load-balancer",
                    "list",
                    "--compartment-id",
                    target_ocid,
                    "--all",
                ],
            ).get("data", [])
            resource_findings, resource_summary = validate_empty_workload_resources(
                instances, load_balancers
            )
            findings.extend(resource_findings)
            summary.update(resource_summary)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        findings.append(
            Finding(
                "oci",
                "oci-read-failed",
                f"Consulta OCI de leitura falhou: {type(exc).__name__}.",
            )
        )
    return findings, summary


def shutil_which(command: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / command
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def print_summary(summary: dict[str, Any]) -> None:
    for key in (
        "profile",
        "region",
        "tenancy",
        "tenancy_name",
        "auth_user",
        "admin_cidr",
        "ssh_public_key",
        "ready_regions",
        "availability_domains",
        "active_compartments",
        "target_compartment",
        "target_compartment_matches",
        "target_compartment_state",
        "target_compartment_ocid",
        "target_compartment_parent",
        "target_compute_shape",
        "target_compute_ocpus",
        "target_compute_memory_gbs",
        "target_boot_volume_size_gbs",
        "payg_budget_required",
        "capacity_report_required",
        "existing_compute_instances",
        "existing_e4_flex_instances",
        "existing_compute_shapes",
        "existing_a1_flex_instances",
        "existing_a1_flex_states",
        "existing_load_balancers",
        "existing_load_balancer_states",
    ):
        if key in summary:
            value = summary[key]
            if isinstance(value, list):
                value = ",".join(value) if value else "(nenhum)"
            print(f"{key}={value}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="EDUDOCS")
    parser.add_argument(
        "--ssh-public-key",
        type=Path,
        default=DEFAULT_SSH_PUBLIC_KEY,
    )
    parser.add_argument("--compartment-name", default="edudocs-ai-prod")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    findings, summary = collect_findings(
        args.profile, args.ssh_public_key.expanduser(), args.compartment_name
    )
    print_summary(summary)
    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.kind}: {finding.message}")
        return 1
    print("READY_FOR_PLAN: readiness OCI validada sem expor segredos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
