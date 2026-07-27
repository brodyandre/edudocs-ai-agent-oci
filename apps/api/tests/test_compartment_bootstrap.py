from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

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


def copy_bootstrap_stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    policy = load_script("check_compartment_bootstrap_policy.py")
    stack = tmp_path / "infrastructure" / "terraform-bootstrap" / "compartment"
    shutil.copytree(ROOT / "infrastructure" / "terraform-bootstrap" / "compartment", stack)
    monkeypatch.setattr(policy, "ROOT", tmp_path)
    monkeypatch.setattr(policy, "STACK", stack)
    monkeypatch.setattr(
        policy,
        "tracked_or_existing_files",
        lambda: [
            path.relative_to(tmp_path).as_posix()
            for path in tmp_path.rglob("*")
            if path.is_file() and ".terraform" not in path.parts
        ],
    )
    return policy, stack


def kinds(findings: list[Any]) -> set[str]:
    return {finding.kind for finding in findings}


def valid_plan(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    after = {
        "name": "edudocs-ai-prod",
        "description": "Recursos de producao do projeto EduDocs AI.",
        "compartment_id": TENANCY,
        "enable_delete": False,
        "freeform_tags": {
            "Project": "EduDocs-AI",
            "Environment": "production",
            "ManagedBy": "Terraform",
            "Purpose": "Application-Workload",
            "CostProfile": "Always-Free-Target",
        },
    }
    if overrides:
        after.update(overrides)
    return {
        "resource_changes": [
            {
                "address": "oci_identity_compartment.edudocs",
                "mode": "managed",
                "type": "oci_identity_compartment",
                "change": {"actions": ["create"], "after": after},
            }
        ],
        "configuration": {
            "root_module": {
                "resources": [
                    {
                        "address": "oci_identity_compartment.edudocs",
                        "type": "oci_identity_compartment",
                        "expressions": {"compartment_id": {"references": ["var.tenancy_ocid"]}},
                    }
                ]
            }
        },
    }


def test_bootstrap_policy_accepts_real_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, _ = copy_bootstrap_stack(tmp_path, monkeypatch)

    assert policy.collect_findings(tmp_path) == []


def test_bootstrap_policy_requires_core_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, stack = copy_bootstrap_stack(tmp_path, monkeypatch)
    (stack / "outputs.tf").unlink()

    assert "missing-file" in kinds(policy.collect_findings(tmp_path))


def test_bootstrap_policy_rejects_wrong_resource_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, stack = copy_bootstrap_stack(tmp_path, monkeypatch)
    (stack / "workload.tf").write_text(
        'resource "oci_core_vcn" "bad" {}\nresource "oci_identity_policy" "bad" {}\n',
        encoding="utf-8",
    )

    result = kinds(policy.collect_findings(tmp_path))

    assert "workload-vcn" in result
    assert "iam-policy" in result


def test_bootstrap_policy_requires_single_compartment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, stack = copy_bootstrap_stack(tmp_path, monkeypatch)
    (stack / "extra.tf").write_text(
        'resource "oci_identity_compartment" "second" {}\n', encoding="utf-8"
    )

    assert "compartment-count" in kinds(policy.collect_findings(tmp_path))


def test_bootstrap_policy_requires_safety_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, stack = copy_bootstrap_stack(tmp_path, monkeypatch)
    main = stack / "main.tf"
    main.write_text(
        main.read_text(encoding="utf-8")
        .replace("enable_delete  = false", "enable_delete  = true")
        .replace("prevent_destroy = true", ""),
        encoding="utf-8",
    )

    result = kinds(policy.collect_findings(tmp_path))

    assert "enable-delete-false" in result
    assert "prevent-destroy" in result


def test_bootstrap_policy_requires_provider_backend_and_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, stack = copy_bootstrap_stack(tmp_path, monkeypatch)
    versions = stack / "versions.tf"
    versions.write_text(
        versions.read_text(encoding="utf-8")
        .replace('backend "local" {}', 'backend "local" { path = "terraform.tfstate" }')
        .replace('version = "~> 8.23.0"', 'version = "~> 7.0.0"'),
        encoding="utf-8",
    )
    main = stack / "main.tf"
    main.write_text(
        main.read_text(encoding="utf-8").replace('Project     = "EduDocs-AI"', ""),
        encoding="utf-8",
    )

    result = kinds(policy.collect_findings(tmp_path))

    assert "provider-version" in result
    assert "backend-local" in result
    assert "backend-path-versioned" in result
    assert "missing-required-tag" in result


def test_bootstrap_policy_requires_variable_and_output_guardrails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, stack = copy_bootstrap_stack(tmp_path, monkeypatch)
    variables = stack / "variables.tf"
    variables.write_text(
        variables.read_text(encoding="utf-8")
        .replace('var.compartment_name == "edudocs-ai-prod"', "true")
        .replace('!strcontains(var.compartment_name, "/")', "true")
        + '\nvariable "enable_delete" {}\n',
        encoding="utf-8",
    )
    outputs = stack / "outputs.tf"
    outputs.write_text(
        outputs.read_text(encoding="utf-8").replace("sensitive   = true", ""),
        encoding="utf-8",
    )

    result = kinds(policy.collect_findings(tmp_path))

    assert "exact-name-validation" in result
    assert "no-slash-name" in result
    assert "forbidden-variable" in result
    assert "compartment-output-sensitive" in result


def test_bootstrap_policy_rejects_sensitive_or_local_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy, stack = copy_bootstrap_stack(tmp_path, monkeypatch)
    fake_private_key = "-----BEGIN " + "PRIVATE KEY-----"
    (stack / "secret.tf").write_text(
        f'locals {{ bad = "{fake_private_key}" }}\n', encoding="utf-8"
    )
    (stack / "terraform.tfvars").write_text('tenancy_ocid = "x"\n', encoding="utf-8")

    result = kinds(policy.collect_findings(tmp_path))

    assert "private-key" in result
    assert "forbidden-versioned-file" in result


def test_bootstrap_plan_accepts_exact_compartment_create() -> None:
    plan_check = load_script("check_compartment_bootstrap_plan.py")

    assert plan_check.collect_findings(valid_plan(), {"tenancy_ocid": TENANCY}) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda plan: plan["resource_changes"].append(
                {"mode": "managed", "type": "oci_core_vcn"}
            ),
            "resource-count",
        ),
        (
            lambda plan: plan["resource_changes"][0].update({"type": "oci_core_vcn"}),
            "resource-type",
        ),
        (
            lambda plan: plan["resource_changes"][0]["change"].update({"actions": ["update"]}),
            "action",
        ),
        (
            lambda plan: plan["resource_changes"][0]["change"]["after"].update({"name": "root"}),
            "name",
        ),
        (
            lambda plan: plan["resource_changes"][0]["change"]["after"].update(
                {"description": "bad"}
            ),
            "description",
        ),
        (
            lambda plan: plan["resource_changes"][0]["change"]["after"].update(
                {"compartment_id": COMPARTMENT}
            ),
            "parent",
        ),
        (
            lambda plan: plan["resource_changes"][0]["change"]["after"].update(
                {"enable_delete": True}
            ),
            "enable-delete",
        ),
        (
            lambda plan: plan["resource_changes"][0]["change"]["after"].update(
                {"freeform_tags": {}}
            ),
            "required-tag",
        ),
    ],
)
def test_bootstrap_plan_rejects_invalid_create_shape(mutate, expected: str) -> None:
    plan_check = load_script("check_compartment_bootstrap_plan.py")
    plan = valid_plan()
    mutate(plan)

    assert expected in kinds(plan_check.collect_findings(plan, {"tenancy_ocid": TENANCY}))


def test_bootstrap_plan_rejects_forbidden_configuration_and_text() -> None:
    plan_check = load_script("check_compartment_bootstrap_plan.py")
    plan = valid_plan()
    plan["configuration"]["root_module"]["resources"].append(
        {"address": "bad", "type": "oci_identity_policy", "expressions": {}}
    )
    plan["planned_values"] = {"root_module": {"values": {"bad": "fingerprint"}}}

    result = kinds(plan_check.collect_findings(plan, {"tenancy_ocid": TENANCY}))

    assert "resource-count" in result
    assert "resource-type" in result
    assert "fingerprint" in result
