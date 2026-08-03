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
variable "tenancy_ocid" {
  validation { condition = can(regex("^ocid1\\\\.tenancy\\\\.oc1\\\\.", var.tenancy_ocid)) }
}
variable "compartment_ocid" {
  description = "OCID do compartment filho dedicado. Root compartment e proibido."
  validation { condition = can(regex("^ocid1\\\\.compartment\\\\.oc1\\\\.", var.compartment_ocid)) }
}
variable "environment" { default = "production" }
variable "compute_shape" { default = "VM.Standard.E4.Flex" }
variable "compute_ocpus" {
  default = 1
  validation { condition = var.compute_ocpus == 1 }
}
variable "compute_memory_gbs" {
  default = 8
  validation { condition = var.compute_memory_gbs == 8 }
}
variable "boot_volume_size_gbs" {
  default = 50
  validation { condition = var.boot_volume_size_gbs == 50 }
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
variable "api_image_ref" {
  validation {
    condition = can(regex(
      "^ghcr\\.io/brodyandre/edudocs-ai-api@sha256:[0-9a-f]{64}$",
      var.api_image_ref,
    ))
  }
}
variable "web_image_ref" {
  validation {
    condition = can(regex(
      "^ghcr\\.io/brodyandre/edudocs-ai-web@sha256:[0-9a-f]{64}$",
      var.web_image_ref,
    ))
  }
}
variable "nginx_image_ref" { default = "nginxinc/nginx-unprivileged:1.27.4-alpine" }
variable "deploy_application" {
  default = true
  validation { condition = var.deploy_application == true }
}
variable "application_host_port" {
  default = 8080
  validation { condition = var.application_host_port == 8080 }
}
variable "application_container_port" {
  default = 8080
  validation { condition = var.application_container_port == 8080 }
}
variable "application_health_path" {
  default = "/health"
  validation { condition = var.application_health_path == "/health" }
}
variable "application_root_dir" { default = "/opt/edudocs" }
variable "application_start_timeout_seconds" { default = 600 }
"""


def valid_checks() -> str:
    return """
check "dedicated_workload_compartment" {
  assert {
    condition = (
      var.compartment_ocid != var.tenancy_ocid
      && can(regex("^ocid1\\\\.compartment\\\\.oc1\\\\.", var.compartment_ocid))
      && var.environment == "production"
    )
    error_message = "Workload production deve usar compartment filho dedicado."
  }
}

check "load_balancer_backend_set_name" {
  assert {
    condition = (
      local.load_balancer_backend_set_name == "edudocs-ai-prod-backend-set"
      && length(local.load_balancer_backend_set_name) >= 1
      && length(local.load_balancer_backend_set_name) <= 32
      && !can(regex("\\\\s", local.load_balancer_backend_set_name))
      && can(regex("^[A-Za-z0-9_-]+$", local.load_balancer_backend_set_name))
    )
    error_message = "Nome seguro do backend set."
  }
}
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
locals {
  backend_set_name = var.backend_set_name
  listener_name = "${var.name_prefix}-http"
}

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
  name = local.backend_set_name
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


def valid_cloud_init() -> str:
    return """
#cloud-config
write_files:
  - path: /opt/edudocs/runtime.env
    permissions: "0600"
    content: |
      ${indent(6, runtime_env_content)}
runcmd:
  - [bash, /usr/local/sbin/edudocs-bootstrap.sh]
systemctl enable edudocs-compose.service
systemctl start edudocs-compose.service
curl -fsS "http://127.0.0.1:${application_host_port}${application_health_path}"
ufw allow from ${public_subnet_cidr} to any port ${application_host_port} proto tcp
/var/lib/edudocs/application-ready
/var/lib/edudocs/cloud-init-complete
"""


def valid_compose_template() -> str:
    return """
services:
  api:
    image: "$${API_IMAGE_REF:?Defina API_IMAGE_REF com digest imutavel sha256}"
    environment:
      EDUDOCS_EMBEDDING_PROVIDER: "$${EDUDOCS_EMBEDDING_PROVIDER:-fake}"
      EDUDOCS_LLM_PROVIDER: "$${EDUDOCS_LLM_PROVIDER:-fake}"
    expose: ["8000"]
    restart: unless-stopped
    read_only: true
    security_opt: [no-new-privileges:true]
    cap_drop: [ALL]
    logging: &default-logging
      options: {max-size: "10m", max-file: "3"}
    healthcheck: {test: ["CMD", "true"]}
  web:
    image: "$${WEB_IMAGE_REF:?Defina WEB_IMAGE_REF com digest imutavel sha256}"
    expose: ["3000"]
    restart: unless-stopped
    read_only: true
    security_opt: [no-new-privileges:true]
    cap_drop: [ALL]
    logging: *default-logging
    healthcheck: {test: ["CMD", "true"]}
  nginx:
    image: ${nginx_image_ref}
    ports:
      - "$${NGINX_PORT:-8080}:${application_container_port}"
    restart: unless-stopped
    read_only: true
    security_opt: [no-new-privileges:true]
    cap_drop: [ALL]
    logging: *default-logging
    healthcheck: {test: ["CMD", "true"]}
"""


def valid_nginx_template() -> str:
    return """
pid /tmp/nginx.pid;
client_body_temp_path /tmp/client_temp;
proxy_temp_path /tmp/proxy_temp;
server {
  listen ${application_container_port};
  location = ${application_health_path} { proxy_pass http://api_upstream/health; }
  location = /ready { proxy_pass http://api_upstream/ready; }
  location /api/ { proxy_pass http://api_upstream; }
}
upstream api_upstream { server api:8000; }
upstream web_upstream { server web:3000; }
"""


def valid_runtime_env_template() -> str:
    return """
API_IMAGE_REF=${api_image_ref}
WEB_IMAGE_REF=${web_image_ref}
EDUDOCS_EMBEDDING_PROVIDER=fake
EDUDOCS_LLM_PROVIDER=fake
NGINX_PORT=${application_host_port}
"""


def valid_systemd_template() -> str:
    return "\n".join(
        [
            "[Unit]",
            "Requires=docker.service",
            "[Service]",
            (
                "ExecStartPre=/usr/bin/docker compose "
                "--env-file ${application_root_dir}/runtime.env "
                "--file ${application_root_dir}/docker-compose.yml config"
            ),
            (
                "ExecStartPre=/usr/bin/docker compose "
                "--env-file ${application_root_dir}/runtime.env "
                "--file ${application_root_dir}/docker-compose.yml pull"
            ),
            (
                "ExecStart=/usr/bin/docker compose "
                "--env-file ${application_root_dir}/runtime.env "
                "--file ${application_root_dir}/docker-compose.yml "
                "up --detach --remove-orphans"
            ),
            (
                "ExecStop=/usr/bin/docker compose "
                "--env-file ${application_root_dir}/runtime.env "
                "--file ${application_root_dir}/docker-compose.yml down"
            ),
        ]
    )


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
        "infrastructure/terraform/checks.tf": valid_checks(),
        "infrastructure/terraform/main.tf": """
module "network" {
  compartment_ocid = var.compartment_ocid
}

module "compute" {
  compartment_ocid = var.compartment_ocid
}

module "load_balancer" {
  compartment_ocid   = var.compartment_ocid
  backend_set_name   = local.load_balancer_backend_set_name
  backend_private_ip = module.compute.private_ip
}

module "object_storage" {
  compartment_ocid = var.compartment_ocid
}
""",
        "infrastructure/terraform/data.tf": "",
        "infrastructure/terraform/locals.tf": (
            'locals { load_balancer_backend_set_name = "edudocs-ai-prod-backend-set" }'
        ),
        "infrastructure/terraform/outputs.tf": "",
        "infrastructure/terraform/terraform.tfvars.example": """
tenancy_ocid = "ocid1.tenancy.oc1..substitua"
# O workload deve usar compartment filho dedicado; root compartment e proibido.
compartment_ocid = "ocid1.compartment.oc1..substitua"
admin_cidr = "203.0.113.10/32"
""",
        "infrastructure/terraform/.terraform.lock.hcl": "# lock",
        "infrastructure/terraform/README.md": "# Terraform",
        "infrastructure/cloud-init/app-server.yaml.tftpl": valid_cloud_init(),
        "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl": (valid_compose_template()),
        "infrastructure/cloud-init/nginx.conf.tftpl": valid_nginx_template(),
        "infrastructure/cloud-init/runtime.env.tftpl": valid_runtime_env_template(),
        "infrastructure/cloud-init/edudocs-compose.service.tftpl": (valid_systemd_template()),
        "scripts/check_runtime_bootstrap.py": "# runtime bootstrap validator",
        "infrastructure/terraform/modules/network/main.tf": valid_network(),
        "infrastructure/terraform/modules/network/variables.tf": "",
        "infrastructure/terraform/modules/network/outputs.tf": "",
        "infrastructure/terraform/modules/compute/main.tf": "shape = var.compute_shape\n",
        "infrastructure/terraform/modules/compute/variables.tf": "",
        "infrastructure/terraform/modules/compute/outputs.tf": "",
        "infrastructure/terraform/modules/load-balancer/main.tf": valid_load_balancer(),
        "infrastructure/terraform/modules/load-balancer/variables.tf": """
variable "backend_set_name" {
  validation {
    condition = (
      var.backend_set_name == "edudocs-ai-prod-backend-set"
      && length(var.backend_set_name) >= 1
      && length(var.backend_set_name) <= 32
      && !can(regex("\\\\s", var.backend_set_name))
      && can(regex("^[A-Za-z0-9_-]+$", var.backend_set_name))
    )
  }
}
""",
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


def test_old_backend_set_name_expression_is_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    lb = tmp_path / "infrastructure/terraform/modules/load-balancer/main.tf"
    lb.write_text(
        lb.read_text(encoding="utf-8").replace(
            "backend_set_name = var.backend_set_name",
            'backend_set_name = "${var.name_prefix}-backend-set"',
        ),
        encoding="utf-8",
    )

    assert "old-backend-set-name" in kinds(policy, tmp_path)


def test_backend_set_name_max_validation_is_required(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/modules/load-balancer/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace(
            "&& length(var.backend_set_name) <= 32", ""
        ),
        encoding="utf-8",
    )

    assert "backend-set-max-validation" in kinds(policy, tmp_path)


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


def test_compute_shape_is_restricted_to_e4_flex(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace(
            "VM.Standard.E4.Flex", "VM.Standard.A1.Flex"
        ),
        encoding="utf-8",
    )

    assert "shape-not-e4" in kinds(policy, tmp_path)


def test_compute_limits_are_preserved(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    text = variables.read_text(encoding="utf-8")
    text = text.replace("default = 1", "default = 2", 1)
    text = text.replace("default = 8", "default = 12", 1)
    text = text.replace("default = 50", "default = 200", 1)
    variables.write_text(text, encoding="utf-8")

    result = kinds(policy, tmp_path)

    assert "cpu-default" in result
    assert "memory-default" in result
    assert "boot-default" in result


def test_e4_profile_validations_are_required(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    text = variables.read_text(encoding="utf-8")
    text = text.replace("var.compute_ocpus == 1", "var.compute_ocpus <= 2")
    text = text.replace("var.compute_memory_gbs == 8", "var.compute_memory_gbs <= 12")
    text = text.replace(
        "var.boot_volume_size_gbs == 50",
        "var.boot_volume_size_gbs >= 50 && var.boot_volume_size_gbs <= 100",
    )
    variables.write_text(text, encoding="utf-8")

    result = kinds(policy, tmp_path)

    assert "cpu-validation" in result
    assert "memory-validation" in result
    assert "boot-validation" in result


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
        "curl https://example.com | sh\nGROQ_API_KEY=x\ngit clone https://example.com/repo.git\n.env\n",
    )
    write_file(tmp_path, "infrastructure/terraform/main.tf", 'private_key = "x"')

    result = kinds(policy, tmp_path)

    assert "curl-pipe-shell" in result
    assert "groq-secret-reference" in result
    assert "git-clone" in result
    assert "cloud-init-env-file" in result
    assert "oci-credential-in-code" in result


def test_runtime_bootstrap_contract_is_required(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(tmp_path, "infrastructure/cloud-init/app-server.yaml.tftpl", "#cloud-config")

    result = kinds(policy, tmp_path)

    assert "cloud-init-systemd" in result
    assert "cloud-init-health" in result
    assert "cloud-init-app-marker" in result
    assert "cloud-init-marker" in result


def test_release_image_variables_reject_defaults_and_missing_validation(
    tmp_path: Path,
) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    text = valid_variables().replace("edudocs-ai-api@sha256:[0-9a-f]{64}", "bad")
    text = text.replace(
        'variable "api_image_ref" {\n  validation',
        'variable "api_image_ref" {\n  default = "latest"\n  validation',
    )
    text = text.replace(
        'variable "web_image_ref" {\n  validation',
        'variable "web_image_ref" {\n  default = "latest"\n  validation',
    )
    variables.write_text(text, encoding="utf-8")

    result = kinds(policy, tmp_path)

    assert "api_image_ref-default" in result
    assert "web_image_ref-default" in result
    assert "api-image-validation" in result


def test_runtime_env_requires_fake_providers(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    runtime_env = tmp_path / "infrastructure/cloud-init/runtime.env.tftpl"
    runtime_env.write_text(
        valid_runtime_env_template()
        .replace("EDUDOCS_EMBEDDING_PROVIDER=fake", "EDUDOCS_EMBEDDING_PROVIDER=oci")
        .replace("EDUDOCS_LLM_PROVIDER=fake", "EDUDOCS_LLM_PROVIDER=groq"),
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "runtime-fake-embedding" in result
    assert "runtime-fake-llm" in result


def test_compose_rejects_latest_wrong_registry_and_public_internal_ports(
    tmp_path: Path,
) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    compose = tmp_path / "infrastructure/cloud-init/docker-compose.prod.yaml.tftpl"
    compose.write_text(
        valid_compose_template()
        .replace("$${API_IMAGE_REF", "docker.io/example/api:latest")
        .replace("$${WEB_IMAGE_REF", "ghcr.io/other/web@sha256:abc")
        + '\nports:\n  - "3000:3000"\n  - "8000:8000"\n',
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "latest-reference" in result
    assert "api-image-env" in result
    assert "web-image-env" in result
    assert "compose-public-dev-port" in result


def test_bootstrap_rejects_docker_login_token_and_clone(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    fake_github_token = "ghp_" + ("a" * 30)
    service = tmp_path / "infrastructure/cloud-init/edudocs-compose.service.tftpl"
    service.write_text(
        valid_systemd_template() + "\ndocker login ghcr.io\n" + f"{fake_github_token}\n",
        encoding="utf-8",
    )
    app = tmp_path / "infrastructure/cloud-init/app-server.yaml.tftpl"
    app.write_text(valid_cloud_init() + "\ngit clone https://example.com/repo.git\n")

    result = kinds(policy, tmp_path)

    assert "docker-login" in result
    assert "github-token" in result
    assert "git-clone" in result


def test_terraform_provisioners_are_rejected(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(
        tmp_path,
        "infrastructure/terraform/modules/compute/provisioners.tf",
        'resource "oci_core_instance" "x" { provisioner "remote-exec" {} }',
    )

    assert "terraform-provisioner" in kinds(policy, tmp_path)


def test_nginx_and_systemd_contracts_are_required(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(
        tmp_path,
        "infrastructure/cloud-init/nginx.conf.tftpl",
        "server { listen 3000; }",
    )
    write_file(
        tmp_path,
        "infrastructure/cloud-init/edudocs-compose.service.tftpl",
        "[Service]\nExecStart=/usr/bin/true\n",
    )

    result = kinds(policy, tmp_path)

    assert "nginx-wrong-port" in result
    assert "nginx-listen-8080" in result
    assert "nginx-health" in result
    assert "systemd-compose-pull" in result
    assert "systemd-runtime-env" in result


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


def test_workload_root_compartment_validation_is_required(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    variables = tmp_path / "infrastructure/terraform/variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8").replace(
            "ocid1\\\\.compartment\\\\.oc1", "ocid1\\\\.(compartment|tenancy)"
        ),
        encoding="utf-8",
    )

    assert "compartment-allows-tenancy" in kinds(policy, tmp_path)


def test_dedicated_compartment_check_is_required(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    (tmp_path / "infrastructure/terraform/checks.tf").write_text(
        'check "dedicated_workload_compartment" {}\n', encoding="utf-8"
    )

    result = kinds(policy, tmp_path)

    assert "check-root-difference" in result
    assert "check-compartment-ocid" in result
    assert "check-production" in result


def test_workload_modules_cannot_receive_tenancy_ocid(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    main = tmp_path / "infrastructure/terraform/main.tf"
    main.write_text(
        main.read_text(encoding="utf-8").replace(
            "compartment_ocid = var.compartment_ocid",
            "compartment_ocid = var.tenancy_ocid",
            1,
        ),
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "network-not-using-compartment" in result
    assert "workload-uses-tenancy" in result
