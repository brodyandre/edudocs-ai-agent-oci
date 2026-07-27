from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load_policy():
    script_path = ROOT / "scripts" / "check_workload_state_policy.py"
    spec = importlib.util.spec_from_file_location("check_workload_state_policy", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_workload_state_policy"] = module
    spec.loader.exec_module(module)
    return module


def write_file(root: Path, path: str, content: str) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")
    return target


def valid_versions() -> str:
    return """
terraform {
  required_version = ">= 1.15.0, < 1.16.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 8.23.0"
    }
  }

  backend "local" {}
}
"""


def write_valid_tree(root: Path) -> None:
    write_file(root, "infrastructure/terraform/versions.tf", valid_versions())
    wrapper = root / "scripts" / "terraform_workload.sh"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "scripts" / "terraform_workload.sh", wrapper)
    wrapper.chmod(0o755)
    write_file(
        root,
        "Makefile",
        """
workload-pre-apply-check:
\tpython3 scripts/check_workload_state_policy.py
""",
    )
    write_file(
        root,
        ".github/workflows/quality.yml",
        """
permissions:
  contents: read
jobs:
  test:
    steps:
      - run: python3 scripts/check_workload_state_policy.py
""",
    )


def kinds(policy, root: Path) -> set[str]:
    return {finding.kind for finding in policy.collect_findings(root)}


def test_workload_state_policy_accepts_valid_configuration(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)

    assert policy.collect_findings(tmp_path) == []


def test_workload_state_policy_rejects_backend_missing(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(tmp_path, "infrastructure/terraform/versions.tf", "terraform {}\n")

    assert "backend-missing" in kinds(policy, tmp_path)


def test_workload_state_policy_rejects_backend_path_inside_repo(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(
        tmp_path,
        "infrastructure/terraform/versions.tf",
        valid_versions().replace('backend "local" {}', 'backend "local" { path = "x.tfstate" }'),
    )

    assert "backend-path-versioned" in kinds(policy, tmp_path)


def test_workload_state_policy_rejects_tf_data_dir_inside_repo(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    wrapper = tmp_path / "scripts/terraform_workload.sh"
    wrapper.write_text(
        wrapper.read_text(encoding="utf-8").replace(
            ".local/share/edudocs/terraform-workload", "infrastructure/terraform/.data"
        ),
        encoding="utf-8",
    )

    assert "tf-data-default" in kinds(policy, tmp_path)


def test_workload_state_policy_rejects_forbidden_workflow_and_makefile(
    tmp_path: Path,
) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    write_file(tmp_path, "Makefile", "apply:\n\tterraform apply -auto-approve\n")
    write_file(
        tmp_path,
        ".github/workflows/quality.yml",
        "permissions:\n  contents: write\nsteps:\n  - run: terraform destroy\n",
    )

    result = kinds(policy, tmp_path)

    assert "make-apply-target" in result
    assert "make-terraform-apply" in result
    assert "make-auto-approve" in result
    assert "workflow-terraform-destroy" in result
    assert "workflow-permission" in result


def test_workload_state_policy_rejects_mutating_state_commands(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    wrapper = tmp_path / "scripts/terraform_workload.sh"
    wrapper.write_text(
        wrapper.read_text(encoding="utf-8")
        + "\n# terraform import\n"
        + "# terraform state rm x\n"
        + "# terraform state mv a b\n"
        + "# terraform state push x\n",
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "terraform-import-command" in result
    assert "state-rm-command" in result
    assert "state-mv-command" in result
    assert "state-push-command" in result


def test_workload_state_policy_rejects_bad_plan_options(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    wrapper = tmp_path / "scripts/terraform_workload.sh"
    wrapper.write_text(
        wrapper.read_text(encoding="utf-8")
        + "\nterraform plan -target=x -refresh=false\nterraform apply -auto-approve\n",
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "target" in result
    assert "refresh-false" in result
    assert "auto-approve" in result


def test_workload_state_policy_rejects_sensitive_content(tmp_path: Path) -> None:
    policy = load_policy()
    write_valid_tree(tmp_path)
    wrapper = tmp_path / "scripts/terraform_workload.sh"
    wrapper.write_text(
        wrapper.read_text(encoding="utf-8")
        + "\n# fingerprint\n# "
        + ("ocid1." + "instance.oc1..real")
        + "\n",
        encoding="utf-8",
    )

    result = kinds(policy, tmp_path)

    assert "credential-word" in result
    assert "real-ocid-risk" in result


def copy_wrapper(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    script = repo / "scripts" / "terraform_workload.sh"
    script.parent.mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "terraform_workload.sh", script)
    script.chmod(0o755)
    (repo / "infrastructure/terraform").mkdir(parents=True)
    return script


def run_wrapper(script: Path, home: Path, *args: str, env_extra: dict[str, str] | None = None):
    env = {**os.environ, "HOME": str(home)}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [str(script), *args],
        cwd=script.parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_wrapper_rejects_unknown_command(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    result = run_wrapper(script, tmp_path / "home", "bogus")

    assert result.returncode == 2
    assert "Comando desconhecido" in result.stderr


def test_wrapper_rejects_home_empty(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    env = {**os.environ, "HOME": ""}
    result = subprocess.run(
        [str(script), "state-list"],
        cwd=script.parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "HOME vazio" in result.stderr


def test_wrapper_rejects_state_or_tf_data_inside_repo(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    repo = script.parents[1]
    home = tmp_path / "home"

    state_result = run_wrapper(
        script,
        home,
        "state-list",
        env_extra={"WORKLOAD_STATE_DIR": str(repo / "state")},
    )
    data_result = run_wrapper(
        script,
        home,
        "state-list",
        env_extra={"WORKLOAD_TF_DATA_DIR": str(repo / "data")},
    )

    assert state_result.returncode == 2
    assert data_result.returncode == 2


def test_wrapper_state_list_is_empty_without_state_file(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    result = run_wrapper(script, tmp_path / "home", "state-list")

    assert result.returncode == 0
    assert result.stdout == ""


def test_wrapper_rejects_apply_without_plan(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    result = run_wrapper(script, tmp_path / "home", "apply-saved-plan")

    assert result.returncode == 2
    assert "Uso: apply-saved-plan" in result.stderr


def test_wrapper_rejects_apply_with_directory(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    plan_dir = tmp_path / "plan.tfplan"
    plan_dir.mkdir()
    result = run_wrapper(script, tmp_path / "home", "apply-saved-plan", str(plan_dir))

    assert result.returncode == 2


def test_wrapper_rejects_apply_plan_outside_tmp(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    outside_tmp = Path("/dev/shm")
    if not outside_tmp.is_dir() or not os.access(outside_tmp, os.W_OK):
        pytest.skip("/dev/shm gravavel indisponivel neste ambiente")
    plan = outside_tmp / f"edudocs-unit-{tmp_path.name}.tfplan"
    plan.write_text("fake", encoding="utf-8")
    plan.chmod(0o600)
    try:
        result = run_wrapper(script, tmp_path / "home", "apply-saved-plan", str(plan))
    finally:
        plan.unlink(missing_ok=True)

    assert result.returncode == 2
    assert "em /tmp" in result.stderr


def test_wrapper_rejects_apply_plan_with_unsafe_permission(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    plan = Path("/tmp") / f"edudocs-unit-{tmp_path.name}.tfplan"
    plan.write_text("fake", encoding="utf-8")
    plan.chmod(0o644)
    try:
        result = run_wrapper(script, tmp_path / "home", "apply-saved-plan", str(plan))
    finally:
        plan.unlink(missing_ok=True)

    assert result.returncode == 2
    assert "permissao 600" in result.stderr


def test_wrapper_rejects_destroy_import_state_mutation_and_bad_options(tmp_path: Path) -> None:
    script = copy_wrapper(tmp_path)
    home = tmp_path / "home"

    for command in ("destroy", "import", "state-rm", "state-mv", "state-push"):
        assert run_wrapper(script, home, command).returncode == 2

    varfile = script.parents[1] / "vars.tfvars"
    varfile.write_text("x = 1\n", encoding="utf-8")
    assert run_wrapper(script, home, "plan", "-target=x", str(varfile)).returncode == 2
    assert run_wrapper(script, home, "plan", "/tmp/x.tfplan", "refresh=false").returncode == 2
