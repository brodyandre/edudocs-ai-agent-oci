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


def write_file(root: Path, path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")


def valid_variables() -> str:
    return """
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
variable "enable_load_balancer" { default = true }
variable "load_balancer_shape" { default = "flexible" }
variable "load_balancer_min_bandwidth_mbps" {
  default = 10
  validation { condition = var.load_balancer_min_bandwidth_mbps == 10 }
}
variable "load_balancer_max_bandwidth_mbps" {
  default = 10
  validation { condition = var.load_balancer_max_bandwidth_mbps == 10 }
}
variable "load_balancer_listener_port" { default = 80 }
variable "load_balancer_backend_port" { default = 8080 }
variable "load_balancer_health_path" { default = "/health" }
"""


def valid_network() -> str:
    return """
resource "oci_core_network_security_group" "app" {}
resource "oci_core_network_security_group" "load_balancer" {}

resource "oci_core_network_security_group_security_rule" "ssh_admin" {
  network_security_group_id = oci_core_network_security_group.app.id
  source = var.admin_cidr
  tcp_options { destination_port_range { min = 22 max = 22 } }
}

resource "oci_core_network_security_group_security_rule" "app_from_load_balancer" {
  network_security_group_id = oci_core_network_security_group.app.id
  source_type = "NETWORK_SECURITY_GROUP"
  source = oci_core_network_security_group.load_balancer.id
  tcp_options { destination_port_range { min = 8080 max = 8080 } }
}

resource "oci_core_network_security_group_security_rule" "load_balancer_http" {
  network_security_group_id = oci_core_network_security_group.load_balancer.id
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 80 max = 80 } }
}

resource "oci_core_network_security_group_security_rule" "load_balancer_to_app" {
  network_security_group_id = oci_core_network_security_group.load_balancer.id
  destination_type = "NETWORK_SECURITY_GROUP"
  destination = oci_core_network_security_group.app.id
  tcp_options { destination_port_range { min = 8080 max = 8080 } }
}
"""


def valid_load_balancer() -> str:
    return """
resource "oci_load_balancer_load_balancer" "this" {
  shape = "flexible"
  is_private = false
  network_security_group_ids = [var.load_balancer_nsg_id]
  shape_details {
    minimum_bandwidth_in_mbps = 10
    maximum_bandwidth_in_mbps = 10
  }
}

resource "oci_load_balancer_backend_set" "app" {
  name = "app"
  policy = "ROUND_ROBIN"
  health_checker {
    protocol = "HTTP"
    port = var.backend_port
    url_path = var.health_path
    return_code = 200
  }
}

resource "oci_load_balancer_backend" "app" {
  ip_address = var.backend_private_ip
  port = var.backend_port
}

resource "oci_load_balancer_listener" "http" {
  protocol = "HTTP"
  port = var.listener_port
}
"""


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
        "infrastructure/terraform/providers.tf": 'provider "oci" {}',
        "infrastructure/terraform/variables.tf": valid_variables(),
        "infrastructure/terraform/main.tf": """
module "load_balancer" {
  backend_private_ip = module.compute.private_ip
}
""",
        "infrastructure/terraform/data.tf": "",
        "infrastructure/terraform/locals.tf": "",
        "infrastructure/terraform/outputs.tf": "",
        "infrastructure/terraform/terraform.tfvars.example": """
tenancy_ocid = "ocid1.tenancy.oc1..substitua"
compartment_ocid = "ocid1.compartment.oc1..substitua"
admin_cidr = "203.0.113.10/32"
""",
        "infrastructure/terraform/.terraform.lock.hcl": "# lock",
        "infrastructure/terraform/README.md": "# Terraform",
        "infrastructure/cloud-init/app-server.yaml.tftpl": (
            "/var/lib/edudocs/cloud-init-complete\n"
        ),
        "infrastructure/terraform/modules/network/main.tf": valid_network(),
        "infrastructure/terraform/modules/network/variables.tf": "",
        "infrastructure/terraform/modules/network/outputs.tf": "",
        "infrastructure/terraform/modules/compute/main.tf": "shape = var.compute_shape\n",
        "infrastructure/terraform/modules/compute/variables.tf": "",
        "infrastructure/terraform/modules/compute/outputs.tf": "",
        "infrastructure/terraform/modules/load-balancer/main.tf": valid_load_balancer(),
        "infrastructure/terraform/modules/load-balancer/variables.tf": "",
        "infrastructure/terraform/modules/load-balancer/outputs.tf": "",
        "infrastructure/terraform/modules/object-storage/main.tf": (
            'access_type = "NoPublicAccess"\n'
        ),
        "infrastructure/terraform/modules/object-storage/variables.tf": "",
        "infrastructure/terraform/modules/object-storage/outputs.tf": "",
        ".github/workflows/quality.yml": "permissions:\n  contents: read\n",
    }
    for path, content in files.items():
        write_file(root, path, content)


def kinds(policy, root: Path) -> set[str]:
    return {finding.kind for finding in policy.collect_findings(root)}


def test_valid_load_balancer_architecture_is_accepted(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)

    assert policy.collect_findings(tmp_path) == []


def test_missing_load_balancer_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(tmp_path, "infrastructure/terraform/modules/load-balancer/main.tf", "")

    result = kinds(policy, tmp_path)

    assert "missing-load-balancer" in result
    assert "load-balancer-count" in result


def test_two_load_balancers_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    lb = tmp_path / "infrastructure/terraform/modules/load-balancer/main.tf"
    lb.write_text(
        lb.read_text(encoding="utf-8")
        + '\nresource "oci_load_balancer_load_balancer" "second" {}\n',
        encoding="utf-8",
    )

    assert "load-balancer-count" in kinds(policy, tmp_path)


def test_invalid_load_balancer_shape_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace('"flexible"', '"100Mbps"', 1),
        encoding="utf-8",
    )

    assert "load_balancer_shape-default" in kinds(policy, tmp_path)


def test_min_bandwidth_above_10_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace("default = 10", "default = 20", 1),
        encoding="utf-8",
    )

    assert "load_balancer_min_bandwidth_mbps-default" in kinds(policy, tmp_path)


def test_max_bandwidth_above_10_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    text = variables.read_text(encoding="utf-8")
    text = text.replace(
        'variable "load_balancer_max_bandwidth_mbps" {\n  default = 10',
        'variable "load_balancer_max_bandwidth_mbps" {\n  default = 20',
    )
    variables.write_text(text, encoding="utf-8")

    assert "load_balancer_max_bandwidth_mbps-default" in kinds(policy, tmp_path)


def test_backend_wrong_port_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    lb = tmp_path / "infrastructure/terraform/modules/load-balancer/main.tf"
    lb.write_text(
        lb.read_text(encoding="utf-8").replace("port = var.backend_port", "port = 80"),
        encoding="utf-8",
    )

    assert "backend-port" in kinds(policy, tmp_path)


def test_listener_wrong_port_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    lb = tmp_path / "infrastructure/terraform/modules/load-balancer/main.tf"
    lb.write_text(
        lb.read_text(encoding="utf-8").replace("port = var.listener_port", "port = 8080"),
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "listener-port" in result
    assert "listener-dev-port" in result


def test_health_path_incorrect_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace('"/health"', '"/ready"', 1),
        encoding="utf-8",
    )

    assert "load_balancer_health_path-default" in kinds(policy, tmp_path)


def test_backend_public_ip_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    main = tmp_path / "infrastructure/terraform/main.tf"
    main.write_text("backend_private_ip = module.compute.public_ip\n", encoding="utf-8")

    result = kinds(policy, tmp_path)

    assert "root-backend-private-ip" in result
    assert "root-backend-public-ip" in result


def test_public_8080_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    network = tmp_path / "infrastructure/terraform/modules/network/main.tf"
    network.write_text(
        network.read_text(encoding="utf-8")
        + """
resource "oci_core_network_security_group_security_rule" "bad_8080" {
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 8080 max = 8080 } }
}
""",
        encoding="utf-8",
    )

    assert "public-8080" in kinds(policy, tmp_path)


def test_public_80_directly_on_vm_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    network = tmp_path / "infrastructure/terraform/modules/network/main.tf"
    network.write_text(
        network.read_text(encoding="utf-8")
        + """
resource "oci_core_network_security_group_security_rule" "bad_vm_80" {
  network_security_group_id = oci_core_network_security_group.app.id
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 80 max = 80 } }
}
""",
        encoding="utf-8",
    )

    assert "app-public-http" in kinds(policy, tmp_path)


def test_single_shared_nsg_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    network = tmp_path / "infrastructure/terraform/modules/network/main.tf"
    network.write_text(
        network.read_text(encoding="utf-8").replace(
            'resource "oci_core_network_security_group" "load_balancer" {}', ""
        ),
        encoding="utf-8",
    )

    assert "missing-lb-nsg" in kinds(policy, tmp_path)


def test_network_load_balancer_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(
        tmp_path,
        "infrastructure/terraform/modules/load-balancer/network-lb.tf",
        'resource "oci_network_load_balancer_network_load_balancer" "bad" {}',
    )

    assert "network-load-balancer" in kinds(policy, tmp_path)


def test_reserved_public_ip_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(
        tmp_path,
        "infrastructure/terraform/modules/load-balancer/public-ip.tf",
        'resource "oci_core_public_ip" "bad" {}',
    )

    assert "reserved-public-ip" in kinds(policy, tmp_path)


def test_compute_shape_is_restricted_to_a1_flex(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace(
            "VM.Standard.A1.Flex", "VM.Standard.E4.Flex"
        ),
        encoding="utf-8",
    )

    assert "shape-not-a1" in kinds(policy, tmp_path)


def test_compute_limits_are_preserved(tmp_path: Path) -> None:
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


def test_public_ssh_and_public_dev_ports_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    network = tmp_path / "infrastructure/terraform/modules/network/main.tf"
    network.write_text(
        network.read_text(encoding="utf-8")
        + """
resource "oci_core_network_security_group_security_rule" "bad_ssh" {
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 22 max = 22 } }
}
resource "oci_core_network_security_group_security_rule" "bad_3000" {
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 3000 max = 3000 } }
}
resource "oci_core_network_security_group_security_rule" "bad_8000" {
  source = "0.0.0.0/0"
  tcp_options { destination_port_range { min = 8000 max = 8000 } }
}
""",
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "ssh-public" in result
    assert "public-dev-port" in result


def test_public_bucket_and_nat_gateway_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    infra = tmp_path / "infrastructure/terraform/modules/object-storage/main.tf"
    infra.write_text(
        'resource "oci_objectstorage_bucket" "bad" {\n'
        '  access_type = "ObjectRead"\n'
        "}\n"
        'resource "oci_core_nat_gateway" "bad" {}\n',
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "public-bucket" in result
    assert "nat-gateway" in result


def test_state_tfvars_plan_and_private_keys_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    for name in ("terraform.tfvars", "prod.tfstate", "run.tfplan", "secret.key"):
        write_file(tmp_path, name, "secret")

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
    write_file(
        tmp_path,
        "infrastructure/cloud-init/app-server.yaml.tftpl",
        "curl https://example.com | sh\nGROQ_API_KEY=x\n.env\n",
    )
    write_file(tmp_path, "infrastructure/terraform/main.tf", 'private_key = "x"')

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
