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
    "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl",
    "infrastructure/cloud-init/nginx.conf.tftpl",
    "infrastructure/cloud-init/runtime.env.tftpl",
    "infrastructure/cloud-init/edudocs-compose.service.tftpl",
    "infrastructure/terraform/versions.tf",
    "infrastructure/terraform/providers.tf",
    "infrastructure/terraform/data.tf",
    "infrastructure/terraform/checks.tf",
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
    "infrastructure/terraform/modules/load-balancer/main.tf",
    "infrastructure/terraform/modules/load-balancer/variables.tf",
    "infrastructure/terraform/modules/load-balancer/outputs.tf",
    "infrastructure/terraform/modules/object-storage/main.tf",
    "infrastructure/terraform/modules/object-storage/variables.tf",
    "infrastructure/terraform/modules/object-storage/outputs.tf",
    "scripts/check_runtime_bootstrap.py",
}

FORBIDDEN_INFRASTRUCTURE_RESOURCES = {
    "oci_core_nat_gateway": "nat-gateway",
    "oci_network_load_balancer": "network-load-balancer",
    "oci_containerengine_cluster": "oke",
    "oci_database": "database",
    "oci_core_public_ip": "reserved-public-ip",
    "reserved_ips": "reserved-public-ip",
    "oci_waf": "waf",
    "oci_waas": "waf",
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
OCI_COMPARTMENT_PREFIX = "ocid1." + "compartment.oc1."
OCI_PLACEHOLDERS = {
    "ocid1." + "tenancy.oc1..substitua",
    "ocid1." + "compartment.oc1..substitua",
    "ocid1." + "image.oc1..substitua",
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


def terraform_joined_text(root: Path) -> str:
    return "\n".join(read_text(path) for path in terraform_text_files(root))


def resource_blocks(root: Path) -> list[tuple[str, str, str, str]]:
    blocks: list[tuple[str, str, str, str]] = []
    pattern = re.compile(r'resource\s+"(?P<type>[^"]+)"\s+"(?P<name>[^"]+)"\s*\{')
    for path in terraform_text_files(root):
        if path.suffix != ".tf":
            continue
        text = read_text(path)
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
            blocks.append(
                (
                    relative(path, root),
                    match.group("type"),
                    match.group("name"),
                    text[match.start() : end],
                )
            )
    return blocks


def named_block(text: str, block_type: str, name: str) -> str | None:
    pattern = re.compile(
        rf'{re.escape(block_type)}\s+"{re.escape(name)}"\s*\{{',
        flags=re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
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
    return text[match.start() : end]


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
        if re.search(r'\bprovisioner\s+"(?:remote-exec|local-exec)"', text):
            findings.append(
                Finding(
                    rel,
                    "terraform-provisioner",
                    "Terraform nao pode usar remote-exec ou local-exec.",
                )
            )
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
    if default_value(text, "compute_shape") != '"VM.Standard.E4.Flex"':
        findings.append(
            Finding(
                relative(variables, root),
                "shape-not-e4",
                "compute_shape deve ter default VM.Standard.E4.Flex.",
            )
        )
    if default_value(text, "compute_ocpus") not in {"1", "1.0"}:
        findings.append(
            Finding(
                relative(variables, root),
                "cpu-default",
                "compute_ocpus deve ter default 1.",
            )
        )
    if default_value(text, "compute_memory_gbs") not in {"8", "8.0"}:
        findings.append(
            Finding(
                relative(variables, root),
                "memory-default",
                "compute_memory_gbs deve ter default 8.",
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
    expected_lb_defaults = {
        "enable_load_balancer": "true",
        "load_balancer_shape": '"flexible"',
        "load_balancer_min_bandwidth_mbps": "10",
        "load_balancer_max_bandwidth_mbps": "10",
        "load_balancer_listener_port": "80",
        "load_balancer_backend_port": "8080",
        "load_balancer_health_path": '"/health"',
    }
    for name, expected in expected_lb_defaults.items():
        if default_value(text, name) != expected:
            findings.append(
                Finding(
                    relative(variables, root),
                    f"{name}-default",
                    f"{name} deve ter default {expected}.",
                )
            )

    if default_value(text, "api_image_ref") is not None:
        findings.append(
            Finding(
                relative(variables, root),
                "api_image_ref-default",
                "api_image_ref nao deve ter default versionado.",
            )
        )
    if default_value(text, "web_image_ref") is not None:
        findings.append(
            Finding(
                relative(variables, root),
                "web_image_ref-default",
                "web_image_ref nao deve ter default versionado.",
            )
        )

    expected_app_defaults = {
        "nginx_image_ref": '"nginxinc/nginx-unprivileged:1.27.4-alpine"',
        "deploy_application": "true",
        "application_host_port": "8080",
        "application_container_port": "8080",
        "application_health_path": '"/health"',
        "application_root_dir": '"/opt/edudocs"',
        "application_start_timeout_seconds": "600",
    }
    for name, expected in expected_app_defaults.items():
        if default_value(text, name) != expected:
            findings.append(
                Finding(
                    relative(variables, root),
                    f"{name}-default",
                    f"{name} deve ter default {expected}.",
                )
            )

    required_variable_text = {
        "api-image-validation": "edudocs-ai-api@sha256:[0-9a-f]{64}",
        "web-image-validation": "edudocs-ai-web@sha256:[0-9a-f]{64}",
        "deploy-application-validation": "var.deploy_application == true",
        "application-host-port-validation": "var.application_host_port == 8080",
        "application-container-port-validation": "var.application_container_port == 8080",
        "application-health-path-validation": 'var.application_health_path == "/health"',
    }
    for kind, needle in required_variable_text.items():
        if needle not in text:
            findings.append(
                Finding(
                    relative(variables, root),
                    kind,
                    "Variavel de bootstrap da aplicacao nao contem validacao esperada.",
                )
            )

    if "var.compute_ocpus == 1" not in text:
        findings.append(
            Finding(
                relative(variables, root),
                "cpu-validation",
                "compute_ocpus deve validar exatamente 1.",
            )
        )
    if "var.compute_memory_gbs == 8" not in text:
        findings.append(
            Finding(
                relative(variables, root),
                "memory-validation",
                "compute_memory_gbs deve validar exatamente 8.",
            )
        )
    if "var.boot_volume_size_gbs == 50" not in text:
        findings.append(
            Finding(
                relative(variables, root),
                "boot-validation",
                "boot_volume_size_gbs deve validar exatamente 50 GB.",
            )
        )
    if "var.load_balancer_min_bandwidth_mbps == 10" not in text:
        findings.append(
            Finding(
                relative(variables, root),
                "lb-min-bandwidth-validation",
                "Load Balancer deve validar minimo exatamente 10 Mbps.",
            )
        )
    if "var.load_balancer_max_bandwidth_mbps == 10" not in text:
        findings.append(
            Finding(
                relative(variables, root),
                "lb-max-bandwidth-validation",
                "Load Balancer deve validar maximo exatamente 10 Mbps.",
            )
        )
    return findings


def find_root_compartment_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    variables = root / "infrastructure" / "terraform" / "variables.tf"
    checks = root / "infrastructure" / "terraform" / "checks.tf"
    example = root / "infrastructure" / "terraform" / "terraform.tfvars.example"
    all_tf = terraform_joined_text(root)

    if variables.is_file():
        text = read_text(variables)
        if "ocid1\\\\.(compartment|tenancy)" in text or "ocid1\\.(compartment|tenancy)" in text:
            findings.append(
                Finding(
                    relative(variables, root),
                    "compartment-allows-tenancy",
                    "compartment_ocid nao pode aceitar tenancy/root.",
                )
            )
        block_match = re.search(
            r'variable\s+"compartment_ocid"\s+\{(?P<body>.*?)(?=\nvariable\s+"|\Z)',
            text,
            flags=re.DOTALL,
        )
        block = block_match.group("body") if block_match else ""
        if "ocid1\\\\.compartment\\\\.oc1" not in block and "ocid1\\.compartment\\.oc1" not in block:
            findings.append(
                Finding(
                    relative(variables, root),
                    "compartment-validation",
                    "compartment_ocid deve validar OCID de compartment.",
                )
            )
        if re.search(
            r"root.*pode ser usado|tenancy.*pode ser usada|root.*aprovado",
            block,
            flags=re.IGNORECASE,
        ):
            findings.append(
                Finding(
                    relative(variables, root),
                    "root-authorized-description",
                    "Descricao de compartment_ocid nao pode autorizar root.",
                )
            )

    if not checks.is_file():
        findings.append(
            Finding(
                "infrastructure/terraform/checks.tf",
                "missing-dedicated-compartment-check",
                "checks.tf deve impedir root compartment no workload.",
            )
        )
    else:
        text = read_text(checks)
        required = {
            "var.compartment_ocid != var.tenancy_ocid": "check-root-difference",
            'regex("^ocid1\\\\.compartment\\\\.oc1\\\\.", var.compartment_ocid)': "check-compartment-ocid",
            'var.environment == "production"': "check-production",
        }
        for needle, kind in required.items():
            if needle not in text:
                findings.append(
                    Finding(
                        relative(checks, root),
                        kind,
                        "Check dedicado do compartment esta incompleto.",
                    )
                )

    if example.is_file():
        text = read_text(example)
        match = re.search(r'(?m)^\s*compartment_ocid\s*=\s*"([^"]+)"', text)
        if match and not match.group(1).startswith(OCI_COMPARTMENT_PREFIX):
            findings.append(
                Finding(
                    relative(example, root),
                    "example-root-compartment",
                    "Exemplo principal deve usar placeholder de compartment, nao tenancy.",
                )
            )
        if "root e proibido" not in text and "root compartment" not in text:
            findings.append(
                Finding(
                    relative(example, root),
                    "example-root-warning",
                    "Exemplo deve documentar que root e proibido para workload.",
                )
            )

    forbidden_escape_hatches = (
        "allow_root_compartment",
        "use_root_compartment",
        "skip_compartment_validation",
    )
    for token in forbidden_escape_hatches:
        if token in all_tf:
            findings.append(
                Finding(
                    "infrastructure/terraform",
                    "root-escape-hatch",
                    f"Variavel/escape hatch proibido: {token}.",
                )
            )

    workload_modules = ("network", "compute", "load_balancer", "object_storage")
    root_main = root / "infrastructure" / "terraform" / "main.tf"
    main_text = read_text(root_main) if root_main.is_file() else ""
    for name in workload_modules:
        block = named_block(main_text, "module", name)
        if block and not re.search(r"compartment_ocid\s*=\s*var\.compartment_ocid", block):
            findings.append(
                Finding(
                    relative(root_main, root),
                    f"{name}-not-using-compartment",
                    "Modulo de workload deve receber var.compartment_ocid.",
                )
            )
    if re.search(r"compartment_ocid\s*=\s*var\.tenancy_ocid", main_text):
        findings.append(
            Finding(
                relative(root_main, root),
                "workload-uses-tenancy",
                "Modulo de workload nao pode receber var.tenancy_ocid.",
            )
        )
    return findings


def find_load_balancer_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    blocks = resource_blocks(root)
    all_tf = terraform_joined_text(root)
    lb_blocks = [
        item for item in blocks if item[1] == "oci_load_balancer_load_balancer"
    ]
    listener_blocks = [
        item for item in blocks if item[1] == "oci_load_balancer_listener"
    ]
    backend_set_blocks = [
        item for item in blocks if item[1] == "oci_load_balancer_backend_set"
    ]
    backend_blocks = [item for item in blocks if item[1] == "oci_load_balancer_backend"]

    if len(lb_blocks) != 1:
        findings.append(
            Finding(
                "infrastructure/terraform/modules/load-balancer/main.tf",
                "load-balancer-count",
                "Deve existir exatamente um oci_load_balancer_load_balancer.",
            )
        )
    if len(listener_blocks) != 1:
        findings.append(
            Finding(
                "infrastructure/terraform/modules/load-balancer/main.tf",
                "listener-count",
                "Deve existir exatamente um listener HTTP.",
            )
        )
    if len(backend_blocks) != 1:
        findings.append(
            Finding(
                "infrastructure/terraform/modules/load-balancer/main.tf",
                "backend-count",
                "Deve existir exatamente um backend.",
            )
        )

    for path, _, _, text in lb_blocks:
        if not re.search(r"shape\s*=\s*(var\.load_balancer_shape|\"flexible\")", text):
            findings.append(
                Finding(path, "lb-shape", "Load Balancer deve usar shape flexible.")
            )
        if not re.search(
            r"minimum_bandwidth_in_mbps\s*=\s*(var\.minimum_bandwidth_in_mbps|10)",
            text,
        ):
            findings.append(
                Finding(path, "lb-min-bandwidth", "Bandwidth minimo deve ser 10 Mbps.")
            )
        if not re.search(
            r"maximum_bandwidth_in_mbps\s*=\s*(var\.maximum_bandwidth_in_mbps|10)",
            text,
        ):
            findings.append(
                Finding(path, "lb-max-bandwidth", "Bandwidth maximo deve ser 10 Mbps.")
            )
        if not re.search(r"is_private\s*=\s*false", text):
            findings.append(
                Finding(path, "lb-public", "Load Balancer deve ser publico.")
            )
        if not re.search(
            r"network_security_group_ids\s*=\s*\[\s*var\.load_balancer_nsg_id\s*\]",
            text,
        ):
            findings.append(
                Finding(path, "lb-nsg", "Load Balancer deve usar NSG exclusivo.")
            )

    for path, _, _, text in backend_set_blocks:
        required = {
            r'policy\s*=\s*"ROUND_ROBIN"': "backend-set-policy",
            r'protocol\s*=\s*"HTTP"': "health-protocol",
            r"port\s*=\s*var\.backend_port": "health-port",
            r"url_path\s*=\s*var\.health_path": "health-path",
            r"return_code\s*=\s*200": "health-return-code",
        }
        for pattern, kind in required.items():
            if not re.search(pattern, text):
                findings.append(
                    Finding(path, kind, "Backend set/health checker fora da politica.")
                )

    for path, _, _, text in backend_blocks:
        if not re.search(r"ip_address\s*=\s*var\.backend_private_ip", text):
            findings.append(
                Finding(
                    path, "backend-private-ip", "Backend deve usar IP privado da VM."
                )
            )
        if re.search(r"ip_address\s*=.*public", text, flags=re.IGNORECASE):
            findings.append(
                Finding(path, "backend-public-ip", "Backend nao pode usar IP publico.")
            )
        if re.search(
            r"\bport\s*=\s*80\b|\bport\s*=\s*3000\b|\bport\s*=\s*8000\b", text
        ):
            findings.append(
                Finding(path, "backend-port", "Backend deve usar somente a porta 8080.")
            )
        if not re.search(r"port\s*=\s*(var\.backend_port|8080)\b", text):
            findings.append(
                Finding(path, "backend-port", "Backend deve usar a porta 8080.")
            )

    for path, _, _, text in listener_blocks:
        if not re.search(r'protocol\s*=\s*"HTTP"', text):
            findings.append(
                Finding(path, "listener-protocol", "Listener deve usar HTTP.")
            )
        if not re.search(r"port\s*=\s*(var\.listener_port|80)\b", text):
            findings.append(
                Finding(path, "listener-port", "Listener deve usar a porta 80.")
            )
        if re.search(r"\bport\s*=\s*(3000|8000|8080)\b", text):
            findings.append(
                Finding(
                    path,
                    "listener-dev-port",
                    "Listener nao pode usar porta de desenvolvimento.",
                )
            )
        if "ssl_configuration" in text:
            findings.append(
                Finding(
                    path, "listener-https", "HTTPS/certificado nao entra nesta entrega."
                )
            )

    if not re.search(r"backend_private_ip\s*=\s*module\.compute\.private_ip", all_tf):
        findings.append(
            Finding(
                "infrastructure/terraform/main.tf",
                "root-backend-private-ip",
                "Modulo Load Balancer deve receber module.compute.private_ip.",
            )
        )
    if re.search(r"backend_private_ip\s*=.*public_ip", all_tf):
        findings.append(
            Finding(
                "infrastructure/terraform/main.tf",
                "root-backend-public-ip",
                "Backend nao pode receber public_ip.",
            )
        )
    return findings


def find_network_and_cost_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    blocks = resource_blocks(root)
    all_tf = terraform_joined_text(root)
    for path, _, _, text in blocks:
        for token, kind in FORBIDDEN_INFRASTRUCTURE_RESOURCES.items():
            if token in text:
                findings.append(
                    Finding(path, kind, f"Recurso proibido nesta entrega: {token}.")
                )
        if re.search(
            r"source\s*=\s*\"0\.0\.0\.0/0\".*?min\s*=\s*22", text, flags=re.DOTALL
        ):
            findings.append(
                Finding(path, "ssh-public", "SSH nao pode ser aberto para 0.0.0.0/0.")
            )
        if re.search(r"admin_cidr\s*=\s*\"0\.0\.0\.0/0\"", text):
            findings.append(
                Finding(path, "admin-cidr-public", "admin_cidr nao pode ser 0.0.0.0/0.")
            )
        for port in ("3000", "8000", "2375", "2376"):
            if re.search(
                rf"source\s*=\s*\"0\.0\.0\.0/0\".*?(min|max)\s*=\s*{port}\b",
                text,
                flags=re.DOTALL,
            ):
                findings.append(
                    Finding(
                        path,
                        "public-dev-port",
                        f"Porta {port} nao deve ser liberada no NSG publico.",
                    )
                )
        if re.search(
            r"source\s*=\s*\"0\.0\.0\.0/0\".*?(min|max)\s*=\s*8080\b",
            text,
            flags=re.DOTALL,
        ):
            findings.append(
                Finding(path, "public-8080", "Porta 8080 nao pode ser publica.")
            )
        if (
            "network_security_group_id = oci_core_network_security_group.app.id" in text
            and re.search(
                r"source\s*=\s*\"0\.0\.0\.0/0\".*?(min|max)\s*=\s*(80|443|8080)\b",
                text,
                flags=re.DOTALL,
            )
        ):
            findings.append(
                Finding(
                    path,
                    "app-public-http",
                    "NSG da aplicacao nao pode receber HTTP/HTTPS/8080 publico.",
                )
            )
        if re.search(
            r'access_type\s*=\s*"(ObjectRead|ObjectReadWithoutListObjects|Public)"',
            text,
        ):
            findings.append(
                Finding(path, "public-bucket", "Bucket nao pode ter acesso publico.")
            )
        if re.search(
            r'public_access_type\s*=\s*"(ObjectRead|ObjectReadWithoutListObjects|Public)"',
            text,
        ):
            findings.append(
                Finding(path, "public-bucket", "Bucket nao pode ter acesso publico.")
            )
    if 'resource "oci_core_network_security_group" "app"' not in all_tf:
        findings.append(
            Finding(
                "infrastructure/terraform/modules/network/main.tf",
                "missing-app-nsg",
                "NSG da aplicacao ausente.",
            )
        )
    if 'resource "oci_core_network_security_group" "load_balancer"' not in all_tf:
        findings.append(
            Finding(
                "infrastructure/terraform/modules/network/main.tf",
                "missing-lb-nsg",
                "NSG do Load Balancer ausente.",
            )
        )
    if not re.search(
        r'source_type\s*=\s*"NETWORK_SECURITY_GROUP"', all_tf
    ) or not re.search(
        r"source\s*=\s*oci_core_network_security_group\.load_balancer\.id", all_tf
    ):
        findings.append(
            Finding(
                "infrastructure/terraform/modules/network/main.tf",
                "app-from-lb-nsg",
                "8080 da aplicacao deve aceitar apenas origem do NSG do Load Balancer.",
            )
        )
    if not re.search(
        r'destination_type\s*=\s*"NETWORK_SECURITY_GROUP"', all_tf
    ) or not re.search(
        r"destination\s*=\s*oci_core_network_security_group\.app\.id", all_tf
    ):
        findings.append(
            Finding(
                "infrastructure/terraform/modules/network/main.tf",
                "lb-to-app-nsg",
                "Egress do Load Balancer deve apontar ao NSG da aplicacao.",
            )
        )
    if "oci_load_balancer_load_balancer" not in all_tf:
        findings.append(
            Finding(
                "infrastructure/terraform/modules/load-balancer/main.tf",
                "missing-load-balancer",
                "Load Balancer obrigatorio ausente.",
            )
        )
    return findings


def find_cloud_init_risks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    cloud_init_dir = root / "infrastructure" / "cloud-init"
    for path in cloud_init_dir.glob("*.tftpl"):
        text = read_text(path)
        rel = relative(path, root)
        if re.search(r"curl\b.*\|\s*(?:sh|bash)", text):
            findings.append(
                Finding(
                    rel, "curl-pipe-shell", "cloud-init nao pode usar curl pipe shell."
                )
            )
        forbidden_patterns = {
            "git-clone": r"\bgit\s+clone\b",
            "docker-login": r"\bdocker\s+login\b",
            "latest-reference": r"(?<![A-Za-z0-9_-])latest(?![A-Za-z0-9_-])",
            "groq-secret-reference": r"\bGROQ_API_KEY\b",
            "github-token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b",
            "github-pat": r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
            "private-key": r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
            "real-ocid-risk": r"\bocid1\.[A-Za-z0-9_.-]+",
        }
        for kind, pattern in forbidden_patterns.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                findings.append(
                    Finding(
                        rel,
                        kind,
                        "Template de bootstrap contem conteudo proibido.",
                    )
                )
        if re.search(r"(?m)(^|/)\.env(?:\s|$)", text):
            findings.append(
                Finding(rel, "cloud-init-env-file", "cloud-init nao deve criar .env.")
            )

    app_server = cloud_init_dir / "app-server.yaml.tftpl"
    compose = cloud_init_dir / "docker-compose.prod.yaml.tftpl"
    nginx = cloud_init_dir / "nginx.conf.tftpl"
    runtime_env = cloud_init_dir / "runtime.env.tftpl"
    service = cloud_init_dir / "edudocs-compose.service.tftpl"

    if app_server.is_file():
        text = read_text(app_server)
        required = {
            "cloud-init-systemd": "systemctl enable edudocs-compose.service",
            "cloud-init-systemd-start": "systemctl start edudocs-compose.service",
            "cloud-init-health": "http://127.0.0.1:${application_host_port}${application_health_path}",
            "cloud-init-app-marker": "/var/lib/edudocs/application-ready",
            "cloud-init-marker": "/var/lib/edudocs/cloud-init-complete",
            "cloud-init-runtime-env-permission": 'permissions: "0600"',
            "cloud-init-load-balancer-only": "ufw allow from ${public_subnet_cidr} to any port ${application_host_port} proto tcp",
        }
        for kind, needle in required.items():
            if needle not in text:
                findings.append(
                    Finding(
                        relative(app_server, root),
                        kind,
                        "cloud-init nao contem contrato obrigatorio de bootstrap.",
                    )
                )

    if compose.is_file():
        text = read_text(compose)
        compose_requirements = {
            "api-image-env": "$${API_IMAGE_REF" in text,
            "web-image-env": "$${WEB_IMAGE_REF" in text,
            "fake-llm-provider": "EDUDOCS_LLM_PROVIDER" in text
            and "fake" in text,
            "fake-embedding-provider": "EDUDOCS_EMBEDDING_PROVIDER" in text
            and "fake" in text,
            "compose-healthcheck": text.count("healthcheck:") >= 3,
            "compose-read-only": text.count("read_only: true") >= 3,
            "compose-cap-drop": text.count("cap_drop:") >= 3,
            "compose-no-new-privileges": text.count("no-new-privileges:true") >= 3,
            "compose-restart-policy": text.count("restart: unless-stopped") >= 3,
            "compose-logging": "max-size" in text and "max-file" in text,
            "nginx-only-host-port": '"$${NGINX_PORT:-8080}:${application_container_port}"'
            in text,
        }
        for kind, passed in compose_requirements.items():
            if not passed:
                findings.append(
                    Finding(
                        relative(compose, root),
                        kind,
                        "docker-compose produtivo nao contem contrato obrigatorio.",
                    )
                )
        if re.search(r'ports:\s*\n\s*-\s*"[0-9$:{}-]*:(?:3000|8000)"', text):
            findings.append(
                Finding(
                    relative(compose, root),
                    "compose-public-dev-port",
                    "Compose produtivo nao pode publicar 3000 ou 8000 no host.",
                )
            )

    if nginx.is_file():
        text = read_text(nginx)
        nginx_requirements = {
            "nginx-listen-8080": "listen ${application_container_port};",
            "nginx-health": "location = ${application_health_path}",
            "nginx-ready": "location = /ready",
            "nginx-api": "location /api/",
            "nginx-api-upstream": "server api:8000;",
            "nginx-web-upstream": "server web:3000;",
        }
        for kind, needle in nginx_requirements.items():
            if needle not in text:
                findings.append(
                    Finding(
                        relative(nginx, root),
                        kind,
                        "Nginx renderizado nao segue contrato esperado.",
                    )
                )
        if re.search(r"listen\s+(3000|8000|80);", text):
            findings.append(
                Finding(
                    relative(nginx, root),
                    "nginx-wrong-port",
                    "Nginx da VM deve escutar somente 8080.",
                )
            )

    if runtime_env.is_file():
        text = read_text(runtime_env)
        runtime_requirements = {
            "runtime-api-image": "API_IMAGE_REF=${api_image_ref}",
            "runtime-web-image": "WEB_IMAGE_REF=${web_image_ref}",
            "runtime-fake-embedding": "EDUDOCS_EMBEDDING_PROVIDER=fake",
            "runtime-fake-llm": "EDUDOCS_LLM_PROVIDER=fake",
            "runtime-nginx-port": "NGINX_PORT=${application_host_port}",
        }
        for kind, needle in runtime_requirements.items():
            if needle not in text:
                findings.append(
                    Finding(
                        relative(runtime_env, root),
                        kind,
                        "runtime.env renderizado nao segue contrato esperado.",
                    )
                )

    if service.is_file():
        text = read_text(service)
        service_requirements = {
            "systemd-docker-required": "Requires=docker.service",
            "systemd-compose-config": " config",
            "systemd-compose-pull": " pull",
            "systemd-compose-up": " up --detach --remove-orphans",
            "systemd-compose-down": " down",
            "systemd-runtime-env": "--env-file ${application_root_dir}/runtime.env",
        }
        for kind, needle in service_requirements.items():
            if needle not in text:
                findings.append(
                    Finding(
                        relative(service, root),
                        kind,
                        "Unidade systemd nao segue contrato esperado.",
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
    for ocid in re.findall(r"ocid1\.[A-Za-z0-9_.-]+", text):
        if ocid not in OCI_PLACEHOLDERS:
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
    findings.extend(find_root_compartment_risks(root))
    findings.extend(find_load_balancer_risks(root))
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
