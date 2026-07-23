from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    script_path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_versions_from_pyproject(tmp_path: Path) -> None:
    audit = load_script("audit_project_readiness")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndependencies = ["fastapi>=0.115,<0.116", "langgraph==0.2.76"]\n',
        encoding="utf-8",
    )

    deps = audit.dependencies_from_pyproject(pyproject)

    assert deps["fastapi"] == ">=0.115,<0.116"
    assert deps["langgraph"] == "==0.2.76"


def test_workspace_clean_and_dirty_are_reported(monkeypatch) -> None:
    audit = load_script("audit_project_readiness")

    def fake_run(args, root=audit.ROOT, timeout=120):
        command = " ".join(args)
        if command == "git status --short":
            return {"ok": True, "output": "", "returncode": 0, "available": True}
        if command == "git branch --show-current":
            return {"ok": True, "output": "main", "returncode": 0, "available": True}
        if command == "git rev-parse HEAD":
            return {"ok": True, "output": "abc123", "returncode": 0, "available": True}
        if command == "git remote get-url origin":
            return {
                "ok": True,
                "output": "https://github.com/x/y.git",
                "returncode": 0,
                "available": True,
            }
        if command.startswith("gh repo view"):
            return {
                "ok": True,
                "output": json.dumps(
                    {
                        "url": "https://github.com/x/y",
                        "visibility": "PUBLIC",
                        "defaultBranchRef": {"name": "main"},
                    }
                ),
                "returncode": 0,
                "available": True,
            }
        return {"ok": True, "output": "ok", "returncode": 0, "available": True}

    monkeypatch.setattr(audit, "run_command", fake_run)
    assert audit.collect_git()["workspace_clean"] is True

    def dirty_run(args, root=audit.ROOT, timeout=120):
        result = fake_run(args, root, timeout)
        if " ".join(args) == "git status --short":
            return {**result, "output": " M arquivo-inesperado.txt"}
        return result

    monkeypatch.setattr(audit, "run_command", dirty_run)
    assert audit.collect_git()["workspace_clean"] is False


def test_parse_test_count_from_outputs() -> None:
    audit = load_script("audit_project_readiness")

    assert audit.parse_test_count("87 passed, 1 warning") == 87
    assert audit.parse_test_count("Tests 55 passed (55)") == 55
    assert audit.parse_test_count("sem contagem") is None


def test_workflow_missing_and_approved(monkeypatch) -> None:
    audit = load_script("audit_project_readiness")
    monkeypatch.setattr(
        audit,
        "run_command",
        lambda *args, **kwargs: {"ok": True, "output": "[]", "returncode": 0, "available": True},
    )

    assert audit.collect_github_actions()["latest"] == {}

    runs = [
        {
            "workflowName": "Quality",
            "status": "completed",
            "conclusion": "success",
            "headSha": "abc",
        }
    ]
    monkeypatch.setattr(
        audit,
        "run_command",
        lambda *args, **kwargs: {
            "ok": True,
            "output": json.dumps(runs),
            "returncode": 0,
            "available": True,
        },
    )

    assert audit.collect_github_actions()["latest"]["Quality"]["conclusion"] == "success"


def test_evidence_present_and_absent(tmp_path: Path) -> None:
    audit = load_script("audit_project_readiness")
    (tmp_path / "docs/evidence").mkdir(parents=True)
    (tmp_path / "docs/evidence/home-hero.png").write_bytes(b"png")

    evidence = audit.collect_evidence(tmp_path)

    assert evidence["home"]["status"] == "presente"
    assert evidence["answer"]["status"] == "pendente"
    assert evidence["oci_application"]["status"] == "reservado para etapa futura"


def test_secret_is_sanitized() -> None:
    audit = load_script("audit_project_readiness")

    fake_token = "gho_" + "1234567890abcdefghijABCD"
    output = audit.sanitize_output(f"Token: {fake_token}")

    assert "gho_1234567890" not in output
    assert "[redacted]" in output
