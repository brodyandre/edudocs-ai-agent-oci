#!/usr/bin/env python3
"""Valida a politica estatica do stack bootstrap do compartment OCI."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "infrastructure" / "terraform-bootstrap" / "compartment"

REQUIRED_FILES = {
    ".terraform.lock.hcl",
    "README.md",
    "main.tf",
    "outputs.tf",
    "providers.tf",
    "terraform.tfvars.example",
    "variables.tf",
    "versions.tf",
}

REQUIRED_TAGS = {
    'Project     = "EduDocs-AI"',
    'Environment = "production"',
    'ManagedBy   = "Terraform"',
    'Purpose     = "Application-Workload"',
    'CostProfile = "Always-Free-Target"',
}

FORBIDDEN_RESOURCE_TYPES = {
    "oci_core_vcn": "workload-vcn",
    "oci_core_instance": "workload-compute",
    "oci_load_balancer_load_balancer": "workload-load-balancer",
    "oci_identity_policy": "iam-policy",
    "oci_identity_group": "iam-group",
    "oci_identity_user": "iam-user",
    "oci_limits_quota": "quota",
    "oci_objectstorage_bucket": "bucket",
    "oci_core_subnet": "workload-subnet",
    "oci_core_network_security_group": "workload-nsg",
}

SECRET_PATTERNS = {
    "github-token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    "github-pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "fingerprint": re.compile(r"\bfingerprint\b", re.IGNORECASE),
    "private-key-path": re.compile(r"\bprivate_key(?:_path)?\b", re.IGNORECASE),
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def terraform_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".terraform" not in path.parts
        and (path.suffix == ".tf" or path.name == "terraform.tfvars.example")
    ]


def resource_blocks(text: str) -> list[tuple[str, str, str]]:
    pattern = re.compile(r'resource\s+"(?P<type>[^"]+)"\s+"(?P<name>[^"]+)"\s*\{')
    blocks: list[tuple[str, str, str]] = []
    for match in pattern.finditer(text):
        depth = 0
        end = match.end()
        for index in range(match.end() - 1, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        blocks.append((match.group("type"), match.group("name"), text[match.start() : end]))
    return blocks


def all_text() -> str:
    return "\n".join(read_text(path) for path in terraform_files(STACK))


def tracked_or_existing_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=False,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def find_required_files() -> list[Finding]:
    findings: list[Finding] = []
    for name in sorted(REQUIRED_FILES):
        if not (STACK / name).is_file():
            findings.append(
                Finding(
                    f"infrastructure/terraform-bootstrap/compartment/{name}",
                    "missing-file",
                    "Arquivo obrigatorio do bootstrap do compartment ausente.",
                )
            )
    return findings


def find_resource_policy() -> list[Finding]:
    findings: list[Finding] = []
    text = all_text()
    resources: list[tuple[str, str, str]] = []
    for path in terraform_files(STACK):
        if path.suffix == ".tf":
            for resource_type, name, block in resource_blocks(read_text(path)):
                resources.append((resource_type, rel(path), block))

    compartments = [item for item in resources if item[0] == "oci_identity_compartment"]
    if len(compartments) != 1:
        findings.append(
            Finding(
                rel(STACK / "main.tf"),
                "compartment-count",
                "Deve existir exatamente um oci_identity_compartment.",
            )
        )
    for resource_type, path, _ in resources:
        if resource_type != "oci_identity_compartment":
            findings.append(
                Finding(
                    path,
                    FORBIDDEN_RESOURCE_TYPES.get(resource_type, "unexpected-resource"),
                    f"Bootstrap nao pode criar {resource_type}.",
                )
            )

    if compartments:
        _, path, block = compartments[0]
        required_text = {
            "compartment-parent": "compartment_id = var.tenancy_ocid",
            "compartment-name": "name           = var.compartment_name",
            "enable-delete-false": "enable_delete  = false",
            "prevent-destroy": "prevent_destroy = true",
            "freeform-tags": "freeform_tags  = local.common_tags",
        }
        for kind, needle in required_text.items():
            if needle not in block:
                findings.append(Finding(path, kind, "Contrato obrigatorio ausente."))

    for tag in REQUIRED_TAGS:
        if tag not in text:
            findings.append(
                Finding(
                    rel(STACK / "main.tf"),
                    "missing-required-tag",
                    "Tag obrigatoria do compartment ausente.",
                )
            )
    return findings


def find_provider_backend_policy() -> list[Finding]:
    findings: list[Finding] = []
    text = all_text()
    checks = {
        "terraform-version": 'required_version = ">= 1.15.0, < 1.16.0"',
        "provider-source": 'source  = "oracle/oci"',
        "provider-version": 'version = "~> 8.23.0"',
        "backend-local": 'backend "local" {}',
        "provider-profile": "config_file_profile = var.config_file_profile",
        "provider-tenancy": "tenancy_ocid        = var.tenancy_ocid",
    }
    for kind, needle in checks.items():
        if needle not in text:
            findings.append(
                Finding(rel(STACK / "versions.tf"), kind, "Provider/backend fora da politica.")
            )
    if re.search(r'backend\s+"local"\s*\{[^}]*\bpath\s*=', text, flags=re.DOTALL):
        findings.append(
            Finding(
                rel(STACK / "versions.tf"),
                "backend-path-versioned",
                "Caminho de state real nao pode ser versionado.",
            )
        )
    return findings


def find_variable_policy() -> list[Finding]:
    variables = STACK / "variables.tf"
    text = read_text(variables) if variables.is_file() else ""
    findings: list[Finding] = []
    required = {
        "tenancy-validation": "ocid1\\\\.tenancy\\\\.oc1",
        "exact-name-validation": 'var.compartment_name == "edudocs-ai-prod"',
        "no-root-name": '"root"',
        "no-tenancy-name": '"tenancy"',
        "no-slash-name": '!strcontains(var.compartment_name, "/")',
        "no-newline-name": '!strcontains(var.compartment_name, "\\n")',
        "description-validation": "length(trimspace(var.compartment_description)) > 0",
        "common-tags-map": 'variable "common_tags"',
    }
    for kind, needle in required.items():
        if needle not in text:
            findings.append(
                Finding(rel(variables), kind, "Validacao obrigatoria ausente.")
            )
    forbidden = ("enable_delete", "prevent_destroy")
    for name in forbidden:
        if re.search(rf'variable\s+"{name}"', text):
            findings.append(
                Finding(
                    rel(variables),
                    "forbidden-variable",
                    f"Nao crie variavel para {name}.",
                )
            )
    return findings


def find_outputs_policy() -> list[Finding]:
    outputs = STACK / "outputs.tf"
    text = read_text(outputs) if outputs.is_file() else ""
    findings: list[Finding] = []
    for name in (
        "compartment_name",
        "compartment_ocid",
        "compartment_lifecycle_state",
        "parent_tenancy_reference",
    ):
        if f'output "{name}"' not in text:
            findings.append(Finding(rel(outputs), "missing-output", f"Output {name} ausente."))
    if 'output "compartment_ocid"' in text and "sensitive   = true" not in text:
        findings.append(
            Finding(rel(outputs), "compartment-output-sensitive", "compartment_ocid deve ser sensitive.")
        )
    if re.search(r'output\s+"(?:tenancy_ocid|user_ocid|fingerprint)"', text):
        findings.append(
            Finding(rel(outputs), "sensitive-output", "Output sensivel proibido.")
        )
    return findings


def find_secret_and_ocid_policy() -> list[Finding]:
    findings: list[Finding] = []
    allowed_ocids = {"ocid1.tenancy.oc1..substitua"}
    for path in terraform_files(STACK):
        text = read_text(path)
        path_rel = rel(path)
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(
                    Finding(path_rel, kind, "Conteudo sensivel proibido no bootstrap.")
                )
        for ocid in re.findall(r"ocid1\.[A-Za-z0-9_.-]+", text):
            if ocid not in allowed_ocids:
                findings.append(
                    Finding(path_rel, "real-ocid-risk", "OCID real nao pode ser versionado.")
                )
    for tracked in tracked_or_existing_files():
        if tracked.startswith("infrastructure/terraform-bootstrap/compartment/"):
            name = Path(tracked).name
            if name == "terraform.tfvars" or name.endswith((".tfstate", ".tfplan", ".pem", ".key")):
                findings.append(
                    Finding(tracked, "forbidden-versioned-file", "Nao versione tfvars, state, plan ou chave.")
                )
    return findings


def collect_findings(root: Path = ROOT) -> list[Finding]:
    del root
    findings: list[Finding] = []
    findings.extend(find_required_files())
    findings.extend(find_resource_policy())
    findings.extend(find_provider_backend_policy())
    findings.extend(find_variable_policy())
    findings.extend(find_outputs_policy())
    findings.extend(find_secret_and_ocid_policy())
    return findings


def main() -> int:
    findings = collect_findings(ROOT)
    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.kind}: {finding.message}")
        return 1
    print("OK: politica do bootstrap do compartment validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
