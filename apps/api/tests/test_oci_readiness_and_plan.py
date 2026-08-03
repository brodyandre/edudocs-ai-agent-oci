from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TENANCY = "ocid1." + "tenancy.oc1..unit"
COMPARTMENT = "ocid1." + "compartment.oc1..unit"
SAFE_BACKEND_SET_NAME = "edudocs-ai-prod-backend-set"
OLD_BACKEND_SET_NAME = "edudocs-ai-production-backend-set"


def load_script(name: str):
    script_path = ROOT / "scripts" / name
    module_name = name.removesuffix(".py")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def minimal_plan(resource_changes: list[dict]) -> dict:
    return {"format_version": "1.2", "resource_changes": resource_changes}


def create_change(address: str, resource_type: str, after: dict) -> dict:
    return {
        "address": address,
        "mode": "managed",
        "type": resource_type,
        "name": address.rsplit(".", 1)[-1],
        "change": {"actions": ["create"], "after": after},
    }


def valid_plan() -> dict:
    compartment_values = {"compartment_id": COMPARTMENT}
    return minimal_plan(
        [
            create_change(
                "module.compute.oci_core_instance.app",
                "oci_core_instance",
                {
                    **compartment_values,
                    "shape": "VM.Standard.E4.Flex",
                    "shape_config": [{"ocpus": 1, "memory_in_gbs": 8}],
                    "source_details": [{"boot_volume_size_in_gbs": 50}],
                },
            ),
            create_change(
                "module.load_balancer.oci_load_balancer_load_balancer.this",
                "oci_load_balancer_load_balancer",
                {
                    **compartment_values,
                    "shape": "flexible",
                    "is_private": False,
                    "shape_details": [
                        {
                            "minimum_bandwidth_in_mbps": 10,
                            "maximum_bandwidth_in_mbps": 10,
                        }
                    ],
                },
            ),
            create_change(
                "module.load_balancer.oci_load_balancer_listener.http",
                "oci_load_balancer_listener",
                {
                    "protocol": "HTTP",
                    "port": 80,
                    "default_backend_set_name": SAFE_BACKEND_SET_NAME,
                },
            ),
            create_change(
                "module.load_balancer.oci_load_balancer_backend.app",
                "oci_load_balancer_backend",
                {
                    "backendset_name": SAFE_BACKEND_SET_NAME,
                    "port": 8080,
                    "ip_address": "10.20.10.10",
                    "backup": False,
                    "offline": False,
                },
            ),
            create_change(
                "module.load_balancer.oci_load_balancer_backend_set.app",
                "oci_load_balancer_backend_set",
                {
                    "name": SAFE_BACKEND_SET_NAME,
                    "policy": "ROUND_ROBIN",
                    "health_checker": [
                        {
                            "protocol": "HTTP",
                            "port": 8080,
                            "url_path": "/health",
                            "return_code": 200,
                        }
                    ]
                },
            ),
        ]
    )


def state_addresses(include_recovery_resources: bool = False) -> list[str]:
    addresses = [
        "data.oci_core_images.ubuntu",
        "data.oci_identity_availability_domains.available",
        "module.compute.oci_core_instance.app",
        "module.load_balancer.oci_load_balancer_load_balancer.this",
        "module.network.oci_core_internet_gateway.this",
        "module.network.oci_core_network_security_group.app",
        "module.network.oci_core_network_security_group.load_balancer",
        "module.network.oci_core_network_security_group_security_rule.app_egress_all",
        "module.network.oci_core_network_security_group_security_rule.app_from_load_balancer",
        "module.network.oci_core_network_security_group_security_rule.load_balancer_http",
        "module.network.oci_core_network_security_group_security_rule.load_balancer_to_app",
        "module.network.oci_core_network_security_group_security_rule.ssh_admin",
        "module.network.oci_core_route_table.public",
        "module.network.oci_core_subnet.public",
        "module.network.oci_core_vcn.this",
    ]
    if include_recovery_resources:
        addresses.extend(
            [
                "module.load_balancer.oci_load_balancer_backend_set.app",
                "module.load_balancer.oci_load_balancer_backend.app",
                "module.load_balancer.oci_load_balancer_listener.http",
            ]
        )
    return addresses


def recovery_plan() -> dict:
    return minimal_plan(valid_plan()["resource_changes"][2:])


def test_plan_audit_accepts_valid_create_plan() -> None:
    plan_check = load_script("check_terraform_plan.py")

    tfvars = {"tenancy_ocid": TENANCY, "compartment_ocid": COMPARTMENT}

    assert plan_check.collect_findings(valid_plan(), tfvars) == []


def test_backend_set_name_contract_accepts_current_name() -> None:
    plan_check = load_script("check_terraform_plan.py")

    assert plan_check.valid_load_balancer_backend_set_name(SAFE_BACKEND_SET_NAME)
    assert len(SAFE_BACKEND_SET_NAME) == 27


def test_backend_set_name_contract_accepts_32_characters() -> None:
    plan_check = load_script("check_terraform_plan.py")

    assert plan_check.valid_load_balancer_backend_set_name_format("a" * 32)


def test_backend_set_name_contract_rejects_invalid_names() -> None:
    plan_check = load_script("check_terraform_plan.py")

    for value in (OLD_BACKEND_SET_NAME, "a" * 33, "", "backend set", "backend/set"):
        assert not plan_check.valid_load_balancer_backend_set_name(value)


def test_plan_audit_rejects_old_backend_set_name() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = valid_plan()
    plan["resource_changes"][4]["change"]["after"]["name"] = OLD_BACKEND_SET_NAME

    kinds = {finding.kind for finding in plan_check.collect_findings(plan)}

    assert "lb-backend-set-name" in kinds


def test_plan_audit_rejects_backend_or_listener_name_mismatch() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = valid_plan()
    plan["resource_changes"][2]["change"]["after"]["default_backend_set_name"] = "other"
    plan["resource_changes"][3]["change"]["after"]["backendset_name"] = "other"

    kinds = {finding.kind for finding in plan_check.collect_findings(plan)}

    assert "lb-listener-backend-set" in kinds
    assert "lb-backend-set-name" in kinds


def test_plan_audit_rejects_forbidden_resources_and_mutations() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = valid_plan()
    plan["resource_changes"].append(
        {
            "address": "bad.nat",
            "mode": "managed",
            "type": "oci_core_nat_gateway",
            "name": "bad",
            "change": {"actions": ["create"], "after": {}},
        }
    )
    plan["resource_changes"][0]["change"]["actions"] = ["delete", "create"]

    kinds = {finding.kind for finding in plan_check.collect_findings(plan)}

    assert "resource-not-allowed" in kinds
    assert "mutating-existing-resource" in kinds


def test_plan_audit_rejects_a1_profile_or_scaled_e4() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = valid_plan()
    instance = plan["resource_changes"][0]["change"]["after"]
    instance["shape"] = "VM.Standard.A1.Flex"
    instance["shape_config"] = [{"ocpus": 2, "memory_in_gbs": 12}]
    instance["source_details"] = [{"boot_volume_size_in_gbs": 100}]

    kinds = {finding.kind for finding in plan_check.collect_findings(plan)}

    assert "compute-shape" in kinds
    assert "compute-ocpus" in kinds
    assert "compute-memory" in kinds
    assert "compute-boot-volume" in kinds


def test_plan_audit_rejects_root_or_mismatched_workload_compartment() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = valid_plan()
    plan["resource_changes"][0]["change"]["after"]["compartment_id"] = TENANCY

    kinds = {
        finding.kind
        for finding in plan_check.collect_findings(
            plan, {"tenancy_ocid": TENANCY, "compartment_ocid": COMPARTMENT}
        )
    }

    assert "workload-root-compartment" in kinds
    assert "workload-compartment-mismatch" in kinds


def test_plan_audit_rejects_tfvars_root_compartment() -> None:
    plan_check = load_script("check_terraform_plan.py")

    kinds = {
        finding.kind
        for finding in plan_check.collect_findings(
            valid_plan(), {"tenancy_ocid": TENANCY, "compartment_ocid": TENANCY}
        )
    }

    assert "tfvars-root-compartment" in kinds
    assert "tfvars-compartment-ocid" in kinds


def test_plan_audit_rejects_public_internal_ports_and_latest() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = valid_plan()
    plan["resource_changes"].append(
        create_change(
            "module.network.oci_core_network_security_group_security_rule.bad",
            "oci_core_network_security_group_security_rule",
            {
                "direction": "INGRESS",
                "source": "0.0.0.0/0",
                "tcp_options": [{"destination_port_range": [{"min": 3000, "max": 3000}]}],
            },
        )
    )
    plan["planned_values"] = {"root_module": {"values": {"image": "repo:latest"}}}

    kinds = {finding.kind for finding in plan_check.collect_findings(plan)}

    assert "public-internal-port" in kinds
    assert "latest-reference" in kinds


def test_recovery_plan_accepts_only_missing_load_balancer_resources() -> None:
    plan_check = load_script("check_terraform_plan.py")

    findings = plan_check.collect_recovery_findings(
        recovery_plan(),
        {"tenancy_ocid": TENANCY, "compartment_ocid": COMPARTMENT},
        state_addresses(),
    )

    assert findings == []


def test_recovery_plan_rejects_empty_state() -> None:
    plan_check = load_script("check_terraform_plan.py")

    kinds = {finding.kind for finding in plan_check.collect_recovery_findings(recovery_plan())}

    assert "state-empty" in kinds


def test_recovery_plan_rejects_compute_create() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = recovery_plan()
    plan["resource_changes"].append(valid_plan()["resource_changes"][0])

    kinds = {
        finding.kind
        for finding in plan_check.collect_recovery_findings(plan, {}, state_addresses())
    }

    assert "recovery-create-not-allowed" in kinds
    assert "recovery-compute-create" in kinds


def test_recovery_plan_rejects_load_balancer_create() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = recovery_plan()
    plan["resource_changes"].append(valid_plan()["resource_changes"][1])

    kinds = {
        finding.kind
        for finding in plan_check.collect_recovery_findings(plan, {}, state_addresses())
    }

    assert "recovery-create-not-allowed" in kinds
    assert "recovery-lb-create" in kinds


def test_recovery_plan_rejects_update_replace_delete() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = recovery_plan()
    plan["resource_changes"][0]["change"]["actions"] = ["update"]
    plan["resource_changes"][1]["change"]["actions"] = ["delete", "create"]
    plan["resource_changes"][2]["change"]["actions"] = ["delete"]

    kinds = {
        finding.kind
        for finding in plan_check.collect_recovery_findings(plan, {}, state_addresses())
    }

    assert "recovery-mutates-existing-resource" in kinds
    assert "recovery-unexpected-action" in kinds


def test_recovery_plan_rejects_unexpected_resource_or_state_type() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = recovery_plan()
    plan["resource_changes"].append(
        create_change("bad.bucket", "oci_objectstorage_bucket", {"compartment_id": COMPARTMENT})
    )

    kinds = {
        finding.kind
        for finding in plan_check.collect_recovery_findings(
            plan, {}, [*state_addresses(), "module.bad.oci_core_nat_gateway.this"]
        )
    }

    assert "recovery-create-not-allowed" in kinds
    assert "state-type-unexpected" in kinds


def test_recovery_plan_rejects_create_for_resource_already_in_state() -> None:
    plan_check = load_script("check_terraform_plan.py")

    kinds = {
        finding.kind
        for finding in plan_check.collect_recovery_findings(
            recovery_plan(), {}, state_addresses(include_recovery_resources=True)
        )
    }

    assert "recovery-create-not-missing" in kinds
    assert "recovery-create-set" in kinds


def test_initial_policy_still_accepts_sixteen_create_plan() -> None:
    plan_check = load_script("check_terraform_plan.py")
    plan = valid_plan()
    for index in range(5, 16):
        plan["resource_changes"].append(
            create_change(
                f"module.network.oci_core_network_security_group_security_rule.rule_{index}",
                "oci_core_network_security_group_security_rule",
                {
                    "direction": "EGRESS",
                    "destination": "0.0.0.0/0",
                    "tcp_options": [],
                },
            )
        )

    assert len(
        [
            item
            for item in plan["resource_changes"]
            if item["change"]["actions"] == ["create"]
        ]
    ) == 16
    assert plan_check.collect_findings(plan) == []


def test_readiness_masks_and_validates_admin_cidr() -> None:
    readiness = load_script("check_oci_readiness.py")

    assert readiness.mask_cidr("8.8.8.8/32") == "8.8.x.x/32"
    assert readiness.validate_admin_cidr("8.8.8.8/32") == []
    assert {finding.kind for finding in readiness.validate_admin_cidr("10.0.0.1/32")} == {
        "non-public-admin-cidr"
    }


def test_readiness_requires_single_active_child_compartment() -> None:
    readiness = load_script("check_oci_readiness.py")
    findings, summary = readiness.validate_target_compartment(
        [
            {
                "name": "edudocs-ai-prod",
                "id": COMPARTMENT,
                "compartment-id": TENANCY,
                "lifecycle-state": "ACTIVE",
            }
        ],
        TENANCY,
        "edudocs-ai-prod",
    )

    assert findings == []
    assert summary["target_compartment_matches"] == 1
    assert summary["target_compartment_state"] == "ACTIVE"


def test_readiness_rejects_missing_duplicate_or_inactive_compartment() -> None:
    readiness = load_script("check_oci_readiness.py")
    inactive = {
        "name": "edudocs-ai-prod",
        "id": COMPARTMENT,
        "compartment-id": TENANCY,
        "lifecycle-state": "CREATING",
    }
    duplicate = {
        "name": "edudocs-ai-prod",
        "id": COMPARTMENT + "2",
        "compartment-id": TENANCY,
        "lifecycle-state": "ACTIVE",
    }

    inactive_kinds = {
        finding.kind
        for finding in readiness.validate_target_compartment(
            [inactive], TENANCY, "edudocs-ai-prod"
        )[0]
    }
    duplicate_kinds = {
        finding.kind
        for finding in readiness.validate_target_compartment(
            [inactive, duplicate], TENANCY, "edudocs-ai-prod"
        )[0]
    }

    assert "target-compartment-not-active" in inactive_kinds
    assert "target-compartment-count" in duplicate_kinds


def test_readiness_rejects_existing_compute_or_load_balancer() -> None:
    readiness = load_script("check_oci_readiness.py")

    findings, summary = readiness.validate_empty_workload_resources(
        [
            {
                "shape": "VM.Standard.E4.Flex",
                "lifecycle-state": "RUNNING",
            },
            {
                "shape": "VM.Standard.A1.Flex",
                "lifecycle-state": "RUNNING",
            },
            {
                "shape": "VM.Standard.A1.Flex",
                "lifecycle-state": "TERMINATED",
            },
        ],
        [
            {
                "lifecycle-state": "ACTIVE",
            },
            {
                "lifecycle-state": "DELETED",
            },
        ],
    )

    assert {finding.kind for finding in findings} == {
        "existing-compute-instance",
        "existing-a1-flex-instance",
        "existing-load-balancer",
    }
    assert summary["existing_compute_instances"] == 2
    assert summary["existing_e4_flex_instances"] == 1
    assert summary["existing_a1_flex_instances"] == 1
    assert summary["existing_load_balancers"] == 1


def test_readiness_accepts_empty_workload_resources() -> None:
    readiness = load_script("check_oci_readiness.py")

    findings, summary = readiness.validate_empty_workload_resources([], [])

    assert findings == []
    assert summary["target_compute_shape"] == "VM.Standard.E4.Flex"
    assert summary["target_compute_ocpus"] == 1
    assert summary["target_compute_memory_gbs"] == 8
    assert summary["target_boot_volume_size_gbs"] == 50
    assert summary["existing_compute_instances"] == 0
    assert summary["existing_e4_flex_instances"] == 0
    assert summary["existing_a1_flex_instances"] == 0
    assert summary["existing_load_balancers"] == 0
