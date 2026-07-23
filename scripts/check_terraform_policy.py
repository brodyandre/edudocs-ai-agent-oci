#!/usr/bin/env python3
"""Valida politica estatica da infraestrutura Terraform OCI."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "infrastructure/cloud-init/app-server.yaml.tftpl",
    "infrastructure/terraform/versions.tf",
    "infrastructure/terraform/providers.tf",
    "infrastructure/terraform/data.tf",
    "infrastructure/terraform/locals.tf",
    "infrastructure/terraform/main.tf",
    "infrastructure/terraform/variables.tf",
    "infrastructure/terraform/outputs.tf",
    "infrastructure/terraform/terraform.tfvars.example",
    "infrastructure/terraform/.terraform.lock.hcl",
    "infrastructure/terraform/README.md",
    "infrastructure/terraform/modules/network/main.tf",
    "infrastructure/terraform/modules/network/variables.tf",
    "infrastructure/terraform/modules/network/outputs.tf",
    "infrastructure/terraform/modules/compute/main.tf",
    "infrastructure/terraform/modules/compute/variables.tf",
    "infrastructure/terraform/modules/compute/outputs.tf",
    "infrastructure/terraform/modules/object-storage/main.tf",
    "infrastructure/terraform/modules/object-storage/variables.tf",
    "infrastructure/terraform/modules/object-storage/outputs.tf",
}

FORBIDDEN_INFRASTRUCTURE_RESOURCES = {
    "oci_core_nat_gateway": "nat-gateway",
    "oci_load_balancer": "load-balancer",
    "oci_containerengine_cluster": "oke",
    "oci_database": "database",
    "VM.GPU": "gpu",
}

FORBIDDEN_VERSIONED_NAMES = {
    "terraform.tfvars",
    "tfplan",
}

FORBIDDEN_VERSIONED_SUFFIXES = {
    ".tfstate",
    ".tfplan",
    ".pem",
    ".key",
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def candidate_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and ".terraform" not in path.parts
    ]


def tracked_or_existing_files(root: Path) -> list[str]:
    if (root / ".git").is_dir():
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            text=False,
        )
        return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    return [relative(path, root) for path in candidate_files(root)]


def terraform_text_files(root: Path) -> list[Path]:
    allowed_suffixes = {".tf", ".tftpl"}
    files: list[Path] = []
    for path in (root / "infrastructure").rglob("*"):
        if path.is_file() and (
            path.suffix in allowed_suffixes or path.name == "terraform.tfvars.example"
        ):
            files.append(path)
    return files


def workflow_files(root: Path) -> list[Path]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    return [path for path in workflows.glob("*.yml")] + [
        path for path in workflows.glob("*.yaml")
    ]


def find_required_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(REQUIRED_FILES):
        if not (root / path).is_file():
            findings.append(
                Finding(
                    path,
                    "missing-file",
                    "Arquivo obrigatorio da entrega Terraform ausente.",
                )
            )
    return findings


def find_forbidden_versioned_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_or_existing_files(root):
        name = Path(path).name
        if path == "infrastructure/terraform/terraform.tfvars.example":
            continue
        if name in FORBIDDEN_VERSIONED_NAMES:
            findings.append(
                Finding(
                    path,
                    "forbidden-versioned-file",
                    "Nao versione tfvars real, state ou plan.",
                )
            )
        if any(name.endswith(suffix) for suffix in FORBIDDEN_VERSIONED_SUFFIXES):
            findings.append(
                Finding(
                    path,
                    "forbidden-versioned-file",
                    "Nao versione state, plan ou chave privada.",
                )
            )
    return findings


def find_workflow_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in workflow_files(root):
        text = read_text(path)
        rel = relative(path, root)
        if re.search(r"\bterraform\s+(apply|destroy)\b", text):
            findings.append(
                Finding(
                    rel,
                    "terraform-mutating-command",
                    "Workflow nao pode executar apply ou destroy.",
                )
            )
        if "-auto-approve" in text:
            findings.append(
                Finding(
                    rel,
                    "terraform-auto-approve",
                    "Workflow nao pode usar -auto-approve.",
                )
            )
        if re.search(r"id-token:\s*write|contents:\s*write", text):
            findings.append(
                Finding(
                    rel,
                    "excessive-workflow-permission",
                    "Workflow de validacao deve usar apenas contents: read.",
                )
            )
    return findings


def find_provider_and_secret_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    tf_files = [path for path in terraform_text_files(root) if path.suffix == ".tf"]
    all_tf = "\n".join(read_text(path) for path in tf_files)

    if 'source  = "oracle/oci"' not in all_tf:
        findings.append(
            Finding(
                "infrastructure/terraform/versions.tf",
                "provider-source",
                "Provider OCI deve usar oracle/oci.",
            )
        )
    if 'version = "~> 8.23.0"' not in all_tf:
        findings.append(
            Finding(
                "infrastructure/terraform/versions.tf",
                "provider-version",
                "Provider OCI deve ficar em ~> 8.23.0.",
            )
        )
    if 'required_version = ">= 1.15.0, < 1.16.0"' not in all_tf:
        findings.append(
            Finding(
                "infrastructure/terraform/versions.tf",
                "terraform-version",
                "Terraform deve ficar em >= 1.15.0, < 1.16.0.",
            )
        )

    for path in tf_files:
        text = read_text(path)
        rel = relative(path, root)
        if re.search(r"\b(user_ocid|fingerprint|private_key_path|private_key)\b", text):
            findings.append(
                Finding(
                    rel,
                    "oci-credential-in-code",
                    "Credenciais OCI nao devem aparecer em Terraform.",
                )
            )
        if re.search(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", text):
            findings.append(
                Finding(
                    rel, "private-key", "Chave privada nao pode aparecer em Terraform."
                )
            )
        if re.search(r"\bGROQ_API_KEY\b", text):
            findings.append(
                Finding(
                    rel,
                    "groq-secret-reference",
                    "GROQ_API_KEY nao deve aparecer em Terraform.",
                )
            )
        if re.search(r"\bocid1\.(?:user|instance|vcn|subnet)\.", text):
            findings.append(
                Finding(
                    rel,
                    "real-ocid-risk",
                    "OCIDs reais nao devem ser fixados em Terraform.",
                )
            )
    return findings


def default_value(text: str, variable_name: str) -> str | None:
    match = re.search(
        rf'variable\s+"{re.escape(variable_name)}"\s+\{{(?P<body>.*?)(?=\nvariable\s+"|\Z)',
        text,
        flags=re.DOTALL,
    )
    if not match:
        return None
    default_match = re.search(
        r"default\s*=\s*(?P<value>\"[^\"]*\"|[-0-9.]+|true|false|null)(?=$|\s|})",
        match.group("body"),
    )
    return default_match.group("value").strip() if default_match else None


def find_limit_risks(root: Path) -> list[Finding]:
    variables = root / "infrastructure" / "terraform" / "variables.tf"
    if not variables.is_file():
        return []
    text = read_text(variables)
    findings: list[Finding] = []
    if default_value(text, "compute_shape") != '"VM.Standard.A1.Flex"':
        findings.append(
            Finding(
                relative(variables, root),
                "shape-not-a1",
                "compute_shape deve ter default VM.Standard.A1.Flex.",
            )
        )
    if default_value(text, "compute_ocpus") not in {"2", "2.0"}:
        findings.append(
            Finding(
                relative(variables, root),
                "cpu-default",
                "compute_ocpus deve ter default 2.",
            )
        )
    if default_value(text, "compute_memory_gbs") not in {"12", "12.0"}:
        findings.append(
            Finding(
                relative(variables, root),
                "memory-default",
                "compute_memory_gbs deve ter default 12.",
            )
        )
    if default_value(text, "boot_volume_size_gbs") not in {"50", "50.0"}:
        findings.append(
            Finding(
                relative(variables, root),
                "boot-default",
                "boot_volume_size_gbs deve ter default 50.",
            )
        )
    if default_value(text, "create_backup_bucket") != "false":
        findings.append(
            Finding(
                relative(variables, root),
                "bucket-default",
                "create_backup_bucket deve iniciar false.",
            )
        )

    if not re.search(
        r"var\.compute_ocpus\s*>\s*0\s*&&\s*var\.compute_ocpus\s*<=\s*2", text
    ):
        findings.append(
            Finding(
                relative(variables, root),
                "cpu-validation",
                "compute_ocpus deve validar maximo 2.",
            )
        )
    if not re.search(
        r"var\.compute_memory_gbs\s*>\s*0\s*&&\s*var\.compute_memory_gbs\s*<=\s*12",
        text,
    ):
        findings.append(
            Finding(
                relative(variables, root),
                "memory-validation",
                "compute_memory_gbs deve validar maximo 12.",
            )
        )
    if not re.search(
        r"var\.boot_volume_size_gbs\s*>=\s*50\s*&&\s*var\.boot_volume_size_gbs\s*<=\s*100",
        text,
    ):
        findings.append(
            Finding(
                relative(variables, root),
                "boot-validation",
                "boot_volume_size_gbs deve validar 50 a 100 GB.",
            )
        )
    return findings


def find_network_and_cost_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in terraform_text_files(root):
        text = read_text(path)
        rel = relative(path, root)
        for token, kind in FORBIDDEN_INFRASTRUCTURE_RESOURCES.items():
            if token in text:
                findings.append(
                    Finding(rel, kind, f"Recurso proibido nesta entrega: {token}.")
                )
        if re.search(
            r"source\s*=\s*\"0\.0\.0\.0/0\".*?min\s*=\s*22", text, flags=re.DOTALL
        ):
            findings.append(
                Finding(rel, "ssh-public", "SSH nao pode ser aberto para 0.0.0.0/0.")
            )
        if re.search(r"admin_cidr\s*=\s*\"0\.0\.0\.0/0\"", text):
            findings.append(
                Finding(rel, "admin-cidr-public", "admin_cidr nao pode ser 0.0.0.0/0.")
            )
        for port in ("3000", "8000", "8080", "2375", "2376"):
            if re.search(rf"min\s*=\s*{port}\b|max\s*=\s*{port}\b", text):
                findings.append(
                    Finding(
                        rel,
                        "public-dev-port",
                        f"Porta {port} nao deve ser liberada no NSG publico.",
                    )
                )
        if re.search(
            r'access_type\s*=\s*"(ObjectRead|ObjectReadWithoutListObjects|Public)"',
            text,
        ):
            findings.append(
                Finding(rel, "public-bucket", "Bucket nao pode ter acesso publico.")
            )
        if re.search(
            r'public_access_type\s*=\s*"(ObjectRead|ObjectReadWithoutListObjects|Public)"',
            text,
        ):
            findings.append(
                Finding(rel, "public-bucket", "Bucket nao pode ter acesso publico.")
            )
    return findings


def find_cloud_init_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in (root / "infrastructure" / "cloud-init").glob("*.tftpl"):
        text = read_text(path)
        rel = relative(path, root)
        if re.search(r"curl\b.*\|\s*(?:sh|bash)", text):
            findings.append(
                Finding(
                    rel, "curl-pipe-shell", "cloud-init nao pode usar curl pipe shell."
                )
            )
        for forbidden in ("git clone", "docker pull", "docker compose", "GROQ_API_KEY"):
            if forbidden in text:
                findings.append(
                    Finding(
                        rel,
                        "cloud-init-side-effect",
                        f"cloud-init nao deve conter {forbidden}.",
                    )
                )
        if re.search(r"(?m)(^|/)\.env\b", text):
            findings.append(
                Finding(rel, "cloud-init-env-file", "cloud-init nao deve criar .env.")
            )
        if "/var/lib/edudocs/cloud-init-complete" not in text:
            findings.append(
                Finding(
                    rel,
                    "cloud-init-marker",
                    "cloud-init deve registrar marcador de conclusao.",
                )
            )
    return findings


def find_example_risks(root: Path) -> list[Finding]:
    example = root / "infrastructure" / "terraform" / "terraform.tfvars.example"
    if not example.is_file():
        return []
    text = "\n".join(
        line
        for line in read_text(example).splitlines()
        if not line.lstrip().startswith("#")
    )
    findings: list[Finding] = []
    if "0.0.0.0/0" in text:
        findings.append(
            Finding(
                relative(example, root),
                "example-public-admin-cidr",
                "Exemplo nao pode sugerir admin_cidr publico.",
            )
        )
    allowed_ocids = {
        "ocid1.tenancy.oc1..substitua",
        "ocid1.compartment.oc1..substitua",
        "ocid1.image.oc1..substitua",
    }
    for ocid in re.findall(r"ocid1\.[A-Za-z0-9_.-]+", text):
        if ocid not in allowed_ocids:
            findings.append(
                Finding(
                    relative(example, root),
                    "real-ocid-in-example",
                    "terraform.tfvars.example deve conter apenas placeholders.",
                )
            )
    return findings


def collect_findings(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(find_required_files(root))
    findings.extend(find_forbidden_versioned_files(root))
    findings.extend(find_workflow_risks(root))
    findings.extend(find_provider_and_secret_risks(root))
    findings.extend(find_limit_risks(root))
    findings.extend(find_network_and_cost_risks(root))
    findings.extend(find_cloud_init_risks(root))
    findings.extend(find_example_risks(root))
    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.path}: {finding.kind}: {finding.message}")


def main() -> int:
    findings = collect_findings(ROOT)
    if findings:
        print_findings(findings)
        return 1
    print("OK: politica Terraform OCI validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
