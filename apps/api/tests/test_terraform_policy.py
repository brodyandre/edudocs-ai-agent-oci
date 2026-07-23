from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_policy():
    script_path = ROOT / "scripts" / "check_terraform_policy.py"
    spec = importlib.util.spec_from_file_location("check_terraform_policy", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_terraform_policy"] = module
    spec.loader.exec_module(module)
    return module


def write_valid_tree(root: Path) -> None:
    files = {
        "infrastructure/terraform/versions.tf": """
terraform {
  required_version = ">= 1.15.0, < 1.16.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 8.23.0"
    }
  }
}
""",
        "infrastructure/terraform/providers.tf": """
provider "oci" {
  region              = var.region
  tenancy_ocid        = var.tenancy_ocid
  config_file_profile = var.config_file_profile
}
""",
        "infrastructure/terraform/variables.tf": """
variable "compute_shape" { default = "VM.Standard.A1.Flex" }
variable "compute_ocpus" {
  default = 2
  validation { condition = var.compute_ocpus > 0 && var.compute_ocpus <= 2 }
}
variable "compute_memory_gbs" {
  default = 12
  validation { condition = var.compute_memory_gbs > 0 && var.compute_memory_gbs <= 12 }
}
variable "boot_volume_size_gbs" {
  default = 50
  validation { condition = var.boot_volume_size_gbs >= 50 && var.boot_volume_size_gbs <= 100 }
}
variable "create_backup_bucket" { default = false }
""",
        "infrastructure/terraform/data.tf": "",
        "infrastructure/terraform/locals.tf": "",
        "infrastructure/terraform/main.tf": "",
        "infrastructure/terraform/outputs.tf": "",
        "infrastructure/terraform/terraform.tfvars.example": """
tenancy_ocid = "ocid1.tenancy.oc1..substitua"
compartment_ocid = "ocid1.compartment.oc1..substitua"
admin_cidr = "203.0.113.10/32"
""",
        "infrastructure/terraform/.terraform.lock.hcl": "# lock",
        "infrastructure/terraform/README.md": "# Terraform",
        "infrastructure/cloud-init/app-server.yaml.tftpl": "/var/lib/edudocs/cloud-init-complete\n",
        "infrastructure/terraform/modules/network/main.tf": """
resource "oci_core_network_security_group_security_rule" "ssh_admin" {
  source = var.admin_cidr
  tcp_options { destination_port_range { min = 22 max = 22 } }
}
resource "oci_core_network_security_group_security_rule" "http" {
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 80 max = 80 } }
}
""",
        "infrastructure/terraform/modules/network/variables.tf": "",
        "infrastructure/terraform/modules/network/outputs.tf": "",
        "infrastructure/terraform/modules/compute/main.tf": "shape = var.compute_shape\n",
        "infrastructure/terraform/modules/compute/variables.tf": "",
        "infrastructure/terraform/modules/compute/outputs.tf": "",
        "infrastructure/terraform/modules/object-storage/main.tf": (
            'access_type = "NoPublicAccess"\n'
        ),
        "infrastructure/terraform/modules/object-storage/variables.tf": "",
        "infrastructure/terraform/modules/object-storage/outputs.tf": "",
        ".github/workflows/quality.yml": "permissions:\n  contents: read\n",
    }
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.strip() + "\n", encoding="utf-8")


def kinds(policy, root: Path) -> set[str]:
    return {finding.kind for finding in policy.collect_findings(root)}


def test_valid_configuration_is_accepted(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)

    assert policy.collect_findings(tmp_path) == []


def test_invalid_shape_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace("VM.Standard.A1.Flex", "VM.Standard.E4.Flex"),
        encoding="utf-8",
    )

    assert "shape-not-a1" in kinds(policy, tmp_path)


def test_cpu_memory_and_boot_defaults_are_limited(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    text = variables.read_text(encoding="utf-8")
    text = text.replace("default = 2", "default = 4", 1)
    text = text.replace("default = 12", "default = 24", 1)
    text = text.replace("default = 50", "default = 200", 1)
    variables.write_text(text, encoding="utf-8")

    result = kinds(policy, tmp_path)

    assert "cpu-default" in result
    assert "memory-default" in result
    assert "boot-default" in result


def test_unrestricted_ssh_and_development_ports_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    network = tmp_path / "infrastructure/terraform/modules/network/main.tf"
    network.write_text(
        """
resource "oci_core_network_security_group_security_rule" "bad" {
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 22 max = 22 } }
}
resource "oci_core_network_security_group_security_rule" "dev3000" {
  tcp_options { destination_port_range { min = 3000 max = 3000 } }
}
resource "oci_core_network_security_group_security_rule" "dev8000" {
  tcp_options { destination_port_range { min = 8000 max = 8000 } }
}
resource "oci_core_network_security_group_security_rule" "dev8080" {
  tcp_options { destination_port_range { min = 8080 max = 8080 } }
}
""",
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "ssh-public" in result
    assert "public-dev-port" in result


def test_public_bucket_and_expensive_resources_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    infra = tmp_path / "infrastructure/terraform/modules/object-storage/main.tf"
    infra.write_text(
        'access_type = "ObjectRead"\n'
        'resource "oci_core_nat_gateway" "bad" {}\n'
        'resource "oci_load_balancer" "bad" {}\n',
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "public-bucket" in result
    assert "nat-gateway" in result
    assert "load-balancer" in result


def test_state_tfvars_plan_and_private_keys_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    for name in ("terraform.tfvars", "prod.tfstate", "run.tfplan", "secret.key"):
        (tmp_path / name).write_text("secret", encoding="utf-8")

    assert "forbidden-versioned-file" in kinds(policy, tmp_path)


def test_apply_destroy_and_auto_approve_workflows_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    workflow = tmp_path / ".github/workflows/quality.yml"
    workflow.write_text(
        "permissions:\n  contents: read\nsteps:\n  - run: terraform apply -auto-approve\n",
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "terraform-mutating-command" in result
    assert "terraform-auto-approve" in result


def test_cloud_init_and_tf_secrets_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    (tmp_path / "infrastructure/cloud-init/app-server.yaml.tftpl").write_text(
        "curl https://example.com | sh\nGROQ_API_KEY=x\n.env\n", encoding="utf-8"
    )
    (tmp_path / "infrastructure/terraform/main.tf").write_text(
        'private_key = "x"\n', encoding="utf-8"
    )

    result = kinds(policy, tmp_path)

    assert "curl-pipe-shell" in result
    assert "cloud-init-side-effect" in result
    assert "cloud-init-env-file" in result
    assert "oci-credential-in-code" in result


def test_allowed_tfvars_example_is_accepted(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    example = tmp_path / "infrastructure/terraform/terraform.tfvars.example"
    example.write_text(
        """
tenancy_ocid = "ocid1.tenancy.oc1..substitua"
compartment_ocid = "ocid1.compartment.oc1..substitua"
image_ocid = "ocid1.image.oc1..substitua"
admin_cidr = "203.0.113.10/32"
""",
        encoding="utf-8",
    )

    assert policy.find_example_risks(tmp_path) == []
