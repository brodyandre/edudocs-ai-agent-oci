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


def collect_findings(profile: str, ssh_public_key: Path) -> tuple[list[Finding], dict[str, Any]]:
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
        active_compartments = [
            item for item in compartments if item.get("lifecycle-state") == "ACTIVE"
        ]
        summary["active_compartments"] = [
            item.get("name", "") for item in active_compartments
        ]
        summary["target_compartment"] = (
            "root tenancy compartment" if not active_compartments else "child compartment"
        )
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
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    findings, summary = collect_findings(args.profile, args.ssh_public_key.expanduser())
    print_summary(summary)
    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.kind}: {finding.message}")
        return 1
    print("OK: readiness OCI validada sem expor segredos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
