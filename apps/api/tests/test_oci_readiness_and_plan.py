from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TENANCY = "ocid1." + "tenancy.oc1..unit"
COMPARTMENT = "ocid1." + "compartment.oc1..unit"


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
                    "shape": "VM.Standard.A1.Flex",
                    "shape_config": [{"ocpus": 2, "memory_in_gbs": 12}],
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
                {"protocol": "HTTP", "port": 80},
            ),
            create_change(
                "module.load_balancer.oci_load_balancer_backend.app",
                "oci_load_balancer_backend",
                {"port": 8080, "ip_address": "10.20.10.10"},
            ),
            create_change(
                "module.load_balancer.oci_load_balancer_backend_set.app",
                "oci_load_balancer_backend_set",
                {
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


def test_plan_audit_accepts_valid_create_plan() -> None:
    plan_check = load_script("check_terraform_plan.py")

    tfvars = {"tenancy_ocid": TENANCY, "compartment_ocid": COMPARTMENT}

    assert plan_check.collect_findings(valid_plan(), tfvars) == []


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


def test_readiness_rejects_existing_a1_or_load_balancer() -> None:
    readiness = load_script("check_oci_readiness.py")

    findings, summary = readiness.validate_empty_workload_resources(
        [
            {
                "shape": "VM.Standard.A1.Flex",
                "lifecycle-state": "RUNNING",
            },
            {
                "shape": "VM.Standard.E2.1.Micro",
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
        "existing-a1-flex-instance",
        "existing-load-balancer",
    }
    assert summary["existing_a1_flex_instances"] == 1
    assert summary["existing_load_balancers"] == 1


def test_readiness_accepts_empty_workload_resources() -> None:
    readiness = load_script("check_oci_readiness.py")

    findings, summary = readiness.validate_empty_workload_resources([], [])

    assert findings == []
    assert summary["existing_a1_flex_instances"] == 0
    assert summary["existing_load_balancers"] == 0
