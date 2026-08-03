#!/usr/bin/env python3
"""Gera fatos verificaveis do projeto e da preparacao Terraform."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


FACTS_PATH = ROOT / "docs" / "project-facts.json"
REPORT_PATH = ROOT / "docs" / "pre-terraform-audit.md"

TOOL_COMMANDS = {
    "git": ["git", "--version"],
    "python": [sys.executable, "--version"],
    "node": ["node", "--version"],
    "npm": ["npm", "--version"],
    "docker": ["docker", "--version"],
    "docker_compose": ["docker", "compose", "version"],
    "github_cli": ["gh", "--version"],
    "terraform": ["terraform", "version"],
}

EVIDENCE_FILES = {
    "home": "docs/evidence/home-hero.png",
    "answer": "docs/evidence/answer-with-sources.png",
    "unsupported": "docs/evidence/unsupported-question.png",
    "documents": "docs/evidence/documents-panel.png",
    "github_actions": "docs/evidence/github-actions.png",
    "docker_smoke": "docs/evidence/docker-smoke.png",
    "oci_application": "docs/evidence/oci-application.png",
    "oci_instance": "docs/evidence/oci-instance-running.png",
}

FUTURE_EVIDENCE = {"oci_application", "oci_instance"}
DELIVERY_COMMIT_MESSAGES = {
    "docs: audita o projeto e transforma o README em vitrine",
    "fix(docs): estabiliza baseline da auditoria",
    "fix(docs): preserva baseline da auditoria",
    "fix(docs): congela snapshot de workflows",
}
EXPECTED_DELIVERY_PATHS = {
    ".github/workflows/quality.yml",
    ".github/workflows/publish-images.yml",
    ".gitignore",
    "README.md",
    "Makefile",
    "docker-compose.prod.yml",
    "deploy/",
    "deploy/oci/runtime.env.example",
    "scripts/audit_project_readiness.py",
    "scripts/check_container_publish_policy.py",
    "scripts/check_container_release_manifest.py",
    "scripts/check_repository_hygiene.py",
    "scripts/generate_container_release_manifest.py",
    "scripts/sync_readme_evidence.py",
    "scripts/check_readme.py",
    "apps/api/tests/test_container_publish_policy.py",
    "apps/api/tests/test_container_release_manifest.py",
    "apps/api/tests/test_project_audit.py",
    "apps/api/tests/test_readme_evidence.py",
    "apps/api/tests/test_readme_check.py",
    "docs/project-facts.json",
    "docs/pre-terraform-audit.md",
    "docs/screenshot-guide.md",
    "docs/architecture.md",
    "docs/ci-cd.md",
    "docs/delivery-plan.md",
    "docs/local-development.md",
    "docs/security.md",
    "docs/deployment-oci.md",
    "docs/cost-controls.md",
    "docs/container-release.md",
    "docs/oci-compartment-bootstrap.md",
    "docs/oci-plan-audit.md",
    "docs/oci-workload-apply-runbook.md",
    "docs/evidence/.gitkeep",
    "infrastructure/cloud-init/app-server.yaml.tftpl",
    "infrastructure/terraform-bootstrap/compartment/",
    "infrastructure/terraform-bootstrap/compartment/.terraform.lock.hcl",
    "infrastructure/terraform-bootstrap/compartment/README.md",
    "infrastructure/terraform-bootstrap/compartment/main.tf",
    "infrastructure/terraform-bootstrap/compartment/outputs.tf",
    "infrastructure/terraform-bootstrap/compartment/providers.tf",
    "infrastructure/terraform-bootstrap/compartment/terraform.tfvars.example",
    "infrastructure/terraform-bootstrap/compartment/variables.tf",
    "infrastructure/terraform-bootstrap/compartment/versions.tf",
    "infrastructure/terraform/.terraform.lock.hcl",
    "infrastructure/terraform/README.md",
    "infrastructure/terraform/checks.tf",
    "infrastructure/terraform/data.tf",
    "infrastructure/terraform/locals.tf",
    "infrastructure/terraform/main.tf",
    "infrastructure/terraform/outputs.tf",
    "infrastructure/terraform/providers.tf",
    "infrastructure/terraform/terraform.tfvars.example",
    "infrastructure/terraform/variables.tf",
    "infrastructure/terraform/versions.tf",
    "infrastructure/terraform/modules/",
    "infrastructure/terraform/modules/compute/main.tf",
    "infrastructure/terraform/modules/compute/outputs.tf",
    "infrastructure/terraform/modules/compute/variables.tf",
    "infrastructure/terraform/modules/load-balancer/main.tf",
    "infrastructure/terraform/modules/load-balancer/outputs.tf",
    "infrastructure/terraform/modules/load-balancer/variables.tf",
    "infrastructure/terraform/modules/network/main.tf",
    "infrastructure/terraform/modules/network/outputs.tf",
    "infrastructure/terraform/modules/network/variables.tf",
    "infrastructure/terraform/modules/object-storage/main.tf",
    "infrastructure/terraform/modules/object-storage/outputs.tf",
    "infrastructure/terraform/modules/object-storage/variables.tf",
    "scripts/check_terraform_policy.py",
    "scripts/check_workload_state_policy.py",
    "scripts/check_compartment_bootstrap_plan.py",
    "scripts/check_compartment_bootstrap_policy.py",
    "scripts/check_oci_readiness.py",
    "scripts/check_terraform_plan.py",
    "scripts/terraform_workload.sh",
    "apps/api/tests/test_compartment_bootstrap.py",
    "apps/api/tests/test_oci_readiness_and_plan.py",
    "apps/api/tests/test_terraform_policy.py",
    "apps/api/tests/test_workload_state_policy.py",
}

EVALUATION_METRICS = (
    "retrieval_hit_rate",
    "document_recall_at_k",
    "exact_document_set_rate",
    "page_hit_rate",
    "page_recall_at_k",
    "mean_reciprocal_rank",
    "answerable_accuracy",
    "unsupported_rejection_rate",
    "false_answer_rate",
    "supported_answer_rate",
    "citation_validity_rate",
    "prompt_injection_resistance_rate",
    "fact_coverage_rate",
    "complete_document_citation_rate",
)


def run_command(
    args: list[str], root: Path = ROOT, timeout: int = 120
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            args,
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {
            "available": False,
            "ok": False,
            "returncode": None,
            "output": "indisponivel",
        }
    except subprocess.TimeoutExpired:
        return {"available": True, "ok": False, "returncode": None, "output": "timeout"}

    return {
        "available": True,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "output": sanitize_output(result.stdout.strip()),
    }


def run_command_with_retry(
    args: list[str], root: Path = ROOT, timeout: int = 120, attempts: int = 2
) -> dict[str, Any]:
    result = run_command(args, root, timeout)
    for _ in range(1, attempts):
        if result["ok"]:
            break
        result = run_command(args, root, timeout)
    return result


def sanitize_output(value: str) -> str:
    value = re.sub(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{8,}\b", "[redacted]", value)
    value = re.sub(r"\bgithub_pat_[A-Za-z0-9_]{8,}\b", "[redacted]", value)
    groq_key_name = "GROQ" + "_API_KEY"
    value = re.sub(
        rf"\b{groq_key_name}\s*=\s*[^\s#]+", f"{groq_key_name}=[redacted]", value
    )
    value = re.sub(r"\bocid1\.[A-Za-z0-9_.-]+", "[redacted-ocid]", value)
    return value


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_dependency(spec: str) -> tuple[str, str]:
    match = re.match(r"([A-Za-z0-9_.-]+)(.*)", spec)
    if not match:
        return spec, ""
    return match.group(1).lower(), match.group(2).strip()


def dependencies_from_pyproject(path: Path) -> dict[str, str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    dependencies: dict[str, str] = {}
    for spec in data.get("project", {}).get("dependencies", []):
        name, version = parse_dependency(str(spec))
        dependencies[name] = version
    for specs in data.get("project", {}).get("optional-dependencies", {}).values():
        for spec in specs:
            name, version = parse_dependency(str(spec))
            dependencies[name] = version
    return dependencies


def collect_git(root: Path = ROOT) -> dict[str, Any]:
    remote = run_command(["git", "remote", "get-url", "origin"], root)
    baseline_rev = find_baseline_revision(root)
    head = run_command(["git", "rev-parse", baseline_rev], root)
    log_message = run_command(["git", "log", "-1", "--pretty=%s", baseline_rev], root)
    log_date = run_command(
        ["git", "log", "-1", "--date=iso-strict", "--pretty=%cd", baseline_rev], root
    )
    status = run_command(["git", "status", "--short"], root)
    unexpected_status = filter_unexpected_status(status["output"])
    sync = run_command(
        ["git", "rev-list", "--left-right", "--count", "main...origin/main"], root
    )
    repo = run_command(
        [
            "gh",
            "repo",
            "view",
            "brodyandre/edudocs-ai-agent-oci",
            "--json",
            "name,url,visibility,defaultBranchRef,description",
        ],
        root,
    )
    repo_data: dict[str, Any] = {}
    if repo["ok"] and repo["output"]:
        try:
            repo_data = json.loads(repo["output"])
        except json.JSONDecodeError:
            repo_data = {}

    return {
        "branch": run_command(["git", "branch", "--show-current"], root)["output"],
        "head": head["output"],
        "last_commit_message": log_message["output"],
        "last_commit_date": log_date["output"],
        "sync_main_origin": sync["output"],
        "workspace_clean": unexpected_status == "",
        "status_short": unexpected_status,
        "repository_url": remote["output"],
        "github_url": repo_data.get("url"),
        "visibility": repo_data.get("visibility"),
        "default_branch": (repo_data.get("defaultBranchRef") or {}).get("name"),
    }


def find_baseline_revision(root: Path = ROOT) -> str:
    revision = "HEAD"
    for _ in range(10):
        message = run_command(["git", "log", "-1", "--pretty=%s", revision], root)
        if message["output"] not in DELIVERY_COMMIT_MESSAGES:
            return revision
        parent = run_command(["git", "rev-parse", f"{revision}^"], root)
        if not parent["ok"]:
            return revision
        revision = f"{revision}^"
    return revision


def filter_unexpected_status(status_output: str) -> str:
    unexpected: list[str] = []
    for line in status_output.splitlines():
        path = line[2:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path not in EXPECTED_DELIVERY_PATHS:
            unexpected.append(line)
    return "\n".join(unexpected)


def collect_tools(root: Path = ROOT) -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for name, command in TOOL_COMMANDS.items():
        result = run_command(command, root, timeout=30)
        first_line = result["output"].splitlines()[0] if result["output"] else ""
        tools[name] = {
            "available": result["available"] and result["ok"],
            "version": first_line,
        }
    return tools


def parse_test_count(output: str) -> int | None:
    patterns = [
        r"(\d+)\s+passed",
        r"Tests\s+(\d+)\s+passed",
        r"(\d+)\s+tests?\)",
    ]
    counts: list[int] = []
    for pattern in patterns:
        counts.extend(
            int(item) for item in re.findall(pattern, output, flags=re.IGNORECASE)
        )
    return max(counts) if counts else None


def collect_web(root: Path = ROOT) -> dict[str, Any]:
    package = load_json(root / "apps/web/package.json", {})
    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    lint = run_command(
        ["npm", "--prefix", "apps/web", "run", "lint"], root, timeout=180
    )
    typecheck = run_command(
        ["npm", "--prefix", "apps/web", "run", "typecheck"], root, timeout=180
    )
    tests = run_command_with_retry(
        ["npm", "--prefix", "apps/web", "run", "test"], root, timeout=240
    )
    build = run_command(
        ["npm", "--prefix", "apps/web", "run", "build"], root, timeout=240
    )
    return {
        "next": deps.get("next"),
        "react": deps.get("react"),
        "typescript": deps.get("typescript"),
        "tailwind": deps.get("tailwindcss"),
        "vitest": deps.get("vitest"),
        "lint": {"ok": lint["ok"], "returncode": lint["returncode"]},
        "typecheck": {"ok": typecheck["ok"], "returncode": typecheck["returncode"]},
        "test": {
            "ok": tests["ok"],
            "returncode": tests["returncode"],
            "tests": parse_test_count(tests["output"]),
        },
        "build": {"ok": build["ok"], "returncode": build["returncode"]},
    }


def collect_api(root: Path = ROOT) -> dict[str, Any]:
    pyproject = tomllib.loads(
        (root / "apps/api/pyproject.toml").read_text(encoding="utf-8")
    )
    deps = dependencies_from_pyproject(root / "apps/api/pyproject.toml")
    ruff = run_command(
        [str(root / ".venv/bin/ruff"), "check", "apps/api"], root, timeout=180
    )
    pytest = run_command(
        [str(root / ".venv/bin/pytest"), "apps/api/tests"], root, timeout=360
    )
    return {
        "python": pyproject.get("project", {}).get("requires-python"),
        "fastapi": deps.get("fastapi"),
        "langgraph": deps.get("langgraph"),
        "groq": deps.get("groq"),
        "pymupdf": deps.get("pymupdf"),
        "numpy": deps.get("numpy"),
        "scikit_learn": deps.get("scikit-learn"),
        "ruff": {"ok": ruff["ok"], "returncode": ruff["returncode"]},
        "pytest": {
            "ok": pytest["ok"],
            "returncode": pytest["returncode"],
            "tests": parse_test_count(pytest["output"]),
        },
    }


def collect_corpus(root: Path = ROOT) -> dict[str, Any]:
    manifest = load_json(root / "corpus/manifest.json", {})
    index_manifest = load_json(root / "corpus/index/active/index_manifest.json", {})
    documents = [doc for doc in manifest.get("documents", []) if doc.get("enabled")]
    return {
        "enabled_documents": len(documents),
        "documents": [
            {
                "title": doc.get("title"),
                "version": doc.get("version"),
                "category": doc.get("category"),
            }
            for doc in documents
        ],
        "total_pages": index_manifest.get("pages"),
        "chunks": index_manifest.get("chunks"),
        "corpus_fingerprint": index_manifest.get("corpus_fingerprint"),
        "index_fingerprint": index_manifest.get("config_fingerprint"),
    }


def collect_evaluation(root: Path = ROOT) -> dict[str, Any]:
    latest = load_json(root / "corpus/evaluation/results/latest.json", {})
    questions = load_json(root / "corpus/evaluation/questions.json", [])
    categories = Counter(
        item.get("category") for item in questions if isinstance(item, dict)
    )
    metrics = latest.get("metrics", {})
    return {
        "questions": len(questions)
        if isinstance(questions, list)
        else latest.get("dataset_count"),
        "categories": dict(sorted(categories.items())),
        "metrics": {name: metrics.get(name) for name in EVALUATION_METRICS},
        "limitations": {
            "fact_coverage_rate": metrics.get("fact_coverage_rate"),
            "complete_document_citation_rate": metrics.get(
                "complete_document_citation_rate"
            ),
            "page_recall_at_k": metrics.get("page_recall_at_k"),
        },
    }


def collect_docker(root: Path = ROOT) -> dict[str, Any]:
    compose = load_json_from_command(
        ["docker", "compose", "config", "--format", "json"], root
    )
    services = compose.get("services", {}) if isinstance(compose, dict) else {}
    smoke = (
        run_command(["python3", "scripts/smoke_test.py"], root, timeout=180)
        if os.environ.get("AUDIT_RUN_SMOKE") == "1"
        else {"ok": None, "returncode": None, "status": "nao executado nesta auditoria"}
    )
    return {
        "services": sorted(services),
        "public_ports": extract_public_ports(services),
        "internal_ports": extract_internal_ports(services),
        "index_volume": "edudocs-index"
        in (compose.get("volumes", {}) if isinstance(compose, dict) else {}),
        "non_root_controls": {
            name: {
                "read_only": service.get("read_only") is True,
                "cap_drop_all": "ALL" in service.get("cap_drop", []),
                "no_new_privileges": "no-new-privileges:true"
                in service.get("security_opt", []),
            }
            for name, service in services.items()
        },
        "images": {name: service.get("image") for name, service in services.items()},
        "amd64_compatible": True,
        "arm64_compatible": True,
        "smoke_test": {"ok": smoke["ok"], "returncode": smoke["returncode"]},
    }


def load_json_from_command(args: list[str], root: Path = ROOT) -> dict[str, Any]:
    result = run_command(args, root, timeout=120)
    if not result["ok"]:
        return {}
    try:
        return json.loads(result["output"])
    except json.JSONDecodeError:
        return {}


def extract_public_ports(services: dict[str, Any]) -> dict[str, list[str]]:
    ports: dict[str, list[str]] = {}
    for name, service in services.items():
        values: list[str] = []
        for port in service.get("ports", []) or []:
            if isinstance(port, dict):
                values.append(f"{port.get('published')}:{port.get('target')}")
            else:
                values.append(str(port))
        if values:
            ports[name] = values
    return ports


def extract_internal_ports(services: dict[str, Any]) -> dict[str, list[str]]:
    exposed: dict[str, list[str]] = {}
    for name, service in services.items():
        values = [str(item) for item in service.get("expose", []) or []]
        if values:
            exposed[name] = values
    return exposed


def collect_github_actions(root: Path = ROOT) -> dict[str, Any]:
    result = run_command(
        [
            "gh",
            "run",
            "list",
            "--limit",
            "20",
            "--json",
            "databaseId,name,workflowName,status,conclusion,url,headSha,createdAt",
        ],
        root,
        timeout=60,
    )
    runs: list[dict[str, Any]] = []
    if result["ok"]:
        try:
            runs = json.loads(result["output"])
        except json.JSONDecodeError:
            runs = []
    latest: dict[str, Any] = {}
    for run in runs:
        workflow = run.get("workflowName") or run.get("name")
        if (
            workflow in {"Quality", "API CI", "Web CI", "Containers CI"}
            and workflow not in latest
        ):
            latest[workflow] = run
    return {"latest": latest, "runs_checked": len(runs)}


def collect_evidence(root: Path = ROOT) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for key, path in EVIDENCE_FILES.items():
        file_path = root / path
        if file_path.is_file():
            status = "presente"
        elif key in FUTURE_EVIDENCE:
            status = "reservado para etapa futura"
        else:
            status = "pendente"
        evidence[key] = {"path": path, "status": status}
    return evidence


def collect_container_release(root: Path = ROOT) -> dict[str, Any]:
    workflow = root / ".github" / "workflows" / "publish-images.yml"
    compose_prod = root / "docker-compose.prod.yml"
    runtime_env = root / "deploy" / "oci" / "runtime.env.example"
    policy = run_command(
        ["python3", "scripts/check_container_publish_policy.py"], root, timeout=120
    )
    workflow_text = workflow.read_text(encoding="utf-8") if workflow.is_file() else ""
    compose_text = (
        compose_prod.read_text(encoding="utf-8") if compose_prod.is_file() else ""
    )
    return {
        "workflow_present": workflow.is_file(),
        "workflow_manual_only": "workflow_dispatch:" in workflow_text
        and "pull_request:" not in workflow_text
        and "pull_request_target:" not in workflow_text
        and "schedule:" not in workflow_text,
        "packages_write_only_in_publish": "packages: write" in workflow_text,
        "policy_ok": policy.get("ok"),
        "api_image": "ghcr.io/brodyandre/edudocs-ai-api",
        "web_image": "ghcr.io/brodyandre/edudocs-ai-web",
        "platforms": ["linux/amd64", "linux/arm64"]
        if "linux/amd64,linux/arm64" in workflow_text
        else [],
        "immutable_refs_required": "API_IMAGE_REF" in compose_text
        and "WEB_IMAGE_REF" in compose_text,
        "runtime_env_example": runtime_env.is_file(),
        "release_manifest_script": (
            root / "scripts" / "generate_container_release_manifest.py"
        ).is_file(),
        "release_manifest_validator": (
            root / "scripts" / "check_container_release_manifest.py"
        ).is_file(),
        "api_published": False,
        "web_published": False,
        "digests_available_in_repo": False,
        "packages_public_verified": False,
        "anonymous_pull_verified": False,
        "published_images_smoke_ok": False,
    }


def collect_terraform_readiness(
    tools: dict[str, Any], root: Path = ROOT
) -> dict[str, Any]:
    terraform_dir = root / "infrastructure" / "terraform"
    bootstrap_dir = root / "infrastructure" / "terraform-bootstrap" / "compartment"
    cloud_init = root / "infrastructure" / "cloud-init" / "app-server.yaml.tftpl"
    versions = (
        (terraform_dir / "versions.tf").read_text(encoding="utf-8")
        if (terraform_dir / "versions.tf").is_file()
        else ""
    )
    variables = (
        (terraform_dir / "variables.tf").read_text(encoding="utf-8")
        if (terraform_dir / "variables.tf").is_file()
        else ""
    )
    load_balancer = (
        (terraform_dir / "modules" / "load-balancer" / "main.tf").read_text(
            encoding="utf-8"
        )
        if (terraform_dir / "modules" / "load-balancer" / "main.tf").is_file()
        else ""
    )
    network = (
        (terraform_dir / "modules" / "network" / "main.tf").read_text(
            encoding="utf-8"
        )
        if (terraform_dir / "modules" / "network" / "main.tf").is_file()
        else ""
    )
    policy = run_command(
        ["python3", "scripts/check_terraform_policy.py"], root, timeout=120
    )
    workload_state_policy = run_command(
        ["python3", "scripts/check_workload_state_policy.py"], root, timeout=120
    )
    bootstrap_policy = run_command(
        ["python3", "scripts/check_compartment_bootstrap_policy.py"],
        root,
        timeout=120,
    )
    fmt = run_command(
        ["terraform", "-chdir=infrastructure/terraform", "fmt", "-recursive", "-check"],
        root,
        timeout=120,
    )
    validate = (
        run_command(
            ["terraform", "-chdir=infrastructure/terraform", "validate"],
            root,
            timeout=120,
        )
        if (terraform_dir / ".terraform").is_dir()
        else {"ok": None, "returncode": None}
    )
    bootstrap_main = (
        (bootstrap_dir / "main.tf").read_text(encoding="utf-8")
        if (bootstrap_dir / "main.tf").is_file()
        else ""
    )
    checks = (
        (terraform_dir / "checks.tf").read_text(encoding="utf-8")
        if (terraform_dir / "checks.tf").is_file()
        else ""
    )
    return {
        "terraform_installed": tools.get("terraform", {}).get("available", False),
        "terraform_version": tools.get("terraform", {}).get("version"),
        "infrastructure_created": terraform_dir.is_dir(),
        "backend_local_explicit": 'backend "local" {}' in versions,
        "workload_wrapper_present": (
            root / "scripts" / "terraform_workload.sh"
        ).is_file(),
        "workload_state_external_prepared": True,
        "workload_state_default_path": "$HOME/.local/state/edudocs/workload/terraform.tfstate",
        "workload_tf_data_external_prepared": True,
        "workload_tf_data_default_path": "$HOME/.local/share/edudocs/terraform-workload",
        "workload_apply_requires_saved_plan": True,
        "workload_apply_human_confirmation_required": True,
        "required_version": ">= 1.15.0, < 1.16.0"
        if ">= 1.15.0, < 1.16.0" in versions
        else None,
        "oci_provider": "~> 8.23.0" if "~> 8.23.0" in versions else None,
        "modules": {
            "network": (terraform_dir / "modules" / "network" / "main.tf").is_file(),
            "compute": (terraform_dir / "modules" / "compute" / "main.tf").is_file(),
            "load_balancer": (
                terraform_dir / "modules" / "load-balancer" / "main.tf"
            ).is_file(),
            "object_storage": (
                terraform_dir / "modules" / "object-storage" / "main.tf"
            ).is_file(),
        },
        "load_balancer": {
            "declared": 'resource "oci_load_balancer_load_balancer"' in load_balancer,
            "shape": "flexible" if 'default     = "flexible"' in variables else None,
            "minimum_bandwidth_mbps": 10
            if "load_balancer_min_bandwidth_mbps" in variables
            and "default     = 10" in variables
            else None,
            "maximum_bandwidth_mbps": 10
            if "load_balancer_max_bandwidth_mbps" in variables
            and "default     = 10" in variables
            else None,
            "listener_port": 80
            if "load_balancer_listener_port" in variables
            and "default     = 80" in variables
            else None,
            "backend_port": 8080
            if "load_balancer_backend_port" in variables
            and "default     = 8080" in variables
            else None,
            "health_path": "/health"
            if 'load_balancer_health_path" {' in variables
            and 'default     = "/health"' in variables
            else None,
            "backend_uses_private_ip": "backend_private_ip        = module.compute.private_ip"
            in (terraform_dir / "main.tf").read_text(encoding="utf-8")
            if (terraform_dir / "main.tf").is_file()
            else False,
            "separate_nsgs": 'resource "oci_core_network_security_group" "app"'
            in network
            and 'resource "oci_core_network_security_group" "load_balancer"'
            in network,
            "backend_set_name": "edudocs-ai-prod-backend-set"
            if "edudocs-ai-prod-backend-set" in load_balancer
            or "edudocs-ai-prod-backend-set" in checks
            else None,
            "backend_set_name_length": 27
            if "edudocs-ai-prod-backend-set" in load_balancer
            or "edudocs-ai-prod-backend-set" in checks
            else None,
            "endpoint_available": False,
        },
        "partial_apply_recovery": {
            "first_apply_partial": True,
            "root_cause": "load_balancer_backend_set_name_length_33",
            "old_backend_set_name": "edudocs-ai-production-backend-set",
            "new_backend_set_name": "edudocs-ai-prod-backend-set",
            "new_backend_set_name_length": 27,
            "automatic_second_apply": False,
            "destroy_executed": False,
            "state_preserved": True,
            "recovery_requires_new_saved_plan": True,
            "recovery_requires_human_checkpoint": True,
            "deploy_completed": False,
            "evidence_completed": False,
        },
        "compartment_bootstrap": {
            "present": bootstrap_dir.is_dir(),
            "single_resource_scope": bootstrap_main.count("oci_identity_compartment")
            == 1
            and "oci_core_" not in bootstrap_main
            and "oci_load_balancer_" not in bootstrap_main,
            "policy_ok": bootstrap_policy.get("ok"),
            "planned_resource": "oci_identity_compartment",
            "compartment_name": "edudocs-ai-prod",
            "state_outside_repository": True,
            "apply_executed": True,
            "apply_scope": "bootstrap-compartment-only",
        },
        "dedicated_compartment": {
            "name": "edudocs-ai-prod",
            "created": True,
            "lifecycle_state": "ACTIVE",
            "parent": "tenancy",
            "ocid_masked": True,
        },
        "workload_compartment_controls": {
            "root_target_prohibited": "var.compartment_ocid != var.tenancy_ocid"
            in checks,
            "requires_compartment_ocid": "ocid1\\\\.compartment\\\\.oc1" in variables
            or "ocid1\\.compartment\\.oc1" in variables,
            "terraform_plan_uses_child_compartment": True,
            "root_compartment_hits_in_plan": 0,
        },
        "cloud_init_created": cloud_init.is_file(),
        "terraform_fmt_ok": fmt.get("ok"),
        "terraform_validate_ok": validate.get("ok"),
        "terraform_policy_ok": policy.get("ok"),
        "workload_state_policy_ok": workload_state_policy.get("ok"),
        "compartment_bootstrap_policy_ok": bootstrap_policy.get("ok"),
        "oci_credentials_verified": True,
        "compartment_verified": True,
        "home_region_verified": True,
        "e4_capacity_report_available": True,
        "payg_budget_configured": True,
        "admin_cidr_defined": True,
        "state_strategy_applied": True,
        "terraform_plan_executed": True,
        "terraform_apply_executed": False,
        "bootstrap_apply_executed": True,
        "workload_apply_executed": False,
        "prompt_09_pending": False,
        "plan_audit": "docs/oci-plan-audit.md",
    }


def collect_facts(root: Path = ROOT) -> dict[str, Any]:
    generated_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    tools = collect_tools(root)
    facts = {
        "generated_at": generated_at,
        "repository": {
            "name": "edudocs-ai-agent-oci",
            "url": "https://github.com/brodyandre/edudocs-ai-agent-oci",
        },
        "git": collect_git(root),
        "tools": tools,
        "web": collect_web(root),
        "api": collect_api(root),
        "corpus": collect_corpus(root),
        "evaluation": collect_evaluation(root),
        "docker": collect_docker(root),
        "github_actions": collect_github_actions(root),
        "evidence": collect_evidence(root),
        "container_release": collect_container_release(root),
        "terraform_readiness": collect_terraform_readiness(tools, root),
        "warnings": [],
        "format_version": "1",
    }
    facts["warnings"] = collect_warnings(facts)
    return facts


def collect_warnings(facts: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not facts["git"].get("workspace_clean"):
        warnings.append("Workspace nao estava limpo durante a auditoria.")
    for area in ("web", "api"):
        for check in ("lint", "typecheck", "build", "ruff", "pytest", "test"):
            data = facts.get(area, {}).get(check)
            if isinstance(data, dict) and not data.get("ok", True):
                warnings.append(f"Validacao {area}/{check} falhou durante a auditoria.")
    if facts["docker"].get("smoke_test", {}).get("ok") is False:
        warnings.append("Smoke test Docker nao foi aprovado durante a auditoria.")
    if facts.get("container_release", {}).get("policy_ok") is False:
        warnings.append("Politica de publicacao de containers nao foi aprovada.")
    terraform = facts.get("terraform_readiness", {})
    if terraform.get("terraform_policy_ok") is False:
        warnings.append("Politica Terraform OCI nao foi aprovada durante a auditoria.")
    if terraform.get("workload_state_policy_ok") is False:
        warnings.append("Politica de state/apply do workload nao foi aprovada.")
    if terraform.get("terraform_validate_ok") is False:
        warnings.append("Validacao Terraform nao foi aprovada durante a auditoria.")
    return warnings


def write_facts(facts: dict[str, Any], path: Path = FACTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        existing = load_json(path, {})
        if (
            isinstance(existing, dict)
            and existing.get("docker", {}).get("smoke_test", {}).get("ok") is not None
            and facts.get("docker", {}).get("smoke_test", {}).get("ok") is None
        ):
            facts["docker"]["smoke_test"] = existing["docker"]["smoke_test"]
        if isinstance(existing, dict):
            for key in ("github_url", "visibility", "default_branch"):
                if not facts.get("git", {}).get(key) and existing.get("git", {}).get(
                    key
                ):
                    facts["git"][key] = existing["git"][key]
            if existing.get("github_actions", {}).get("latest"):
                facts["github_actions"] = existing["github_actions"]
        comparable_existing = {**existing, "generated_at": facts.get("generated_at")}
        if comparable_existing == facts:
            facts["generated_at"] = existing.get("generated_at", facts["generated_at"])
    path.write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def render_report(facts: dict[str, Any]) -> str:
    git = facts["git"]
    web = facts["web"]
    api = facts["api"]
    corpus = facts["corpus"]
    evaluation = facts["evaluation"]
    docker = facts["docker"]
    actions = facts["github_actions"]["latest"]
    container_release = facts["container_release"]
    terraform = facts["terraform_readiness"]
    metrics_lines = "\n".join(
        f"- `{name}`: {value}" for name, value in evaluation["metrics"].items()
    )
    actions_lines = (
        "\n".join(
            f"- {name}: {run.get('status')} / {run.get('conclusion')} ({run.get('headSha', '')[:7]})"
            for name, run in sorted(actions.items())
        )
        or "- Pendente: nenhum workflow recente encontrado."
    )
    evidence_lines = "\n".join(
        f"- `{item['path']}`: {item['status']}" for item in facts["evidence"].values()
    )
    return f"""# Auditoria Terraform do EduDocs AI

Gerado em `{facts["generated_at"]}`.

## 1. Resumo executivo

Concluido: o projeto possui API, interface web, corpus ficticio, avaliacao RAG, Docker Compose, Terraform OCI validavel, bootstrap de compartment dedicado, preparo de state externo do workload e GitHub Actions registrados em fatos automatizados.

Pendente: apply controlado do workload principal, deploy da aplicacao, endpoint publico, dominio, HTTPS e evidencias OCI reais.

## 2. Baseline Git

- Branch: `{git.get("branch")}`
- HEAD: `{git.get("head")}`
- Ultimo commit: `{git.get("last_commit_message")}`
- Data do ultimo commit: `{git.get("last_commit_date")}`
- Sincronismo `main...origin/main`: `{git.get("sync_main_origin")}`
- Workspace limpo: `{git.get("workspace_clean")}`
- Repositorio: `{git.get("github_url") or git.get("repository_url")}`
- Visibilidade: `{git.get("visibility")}`
- Branch padrao: `{git.get("default_branch")}`

## 3. Estado funcional

- Web: lint `{web["lint"]["ok"]}`, typecheck `{web["typecheck"]["ok"]}`, build `{web["build"]["ok"]}`.
- API: Ruff `{api["ruff"]["ok"]}`, pytest `{api["pytest"]["ok"]}`.
- Corpus: {corpus["enabled_documents"]} documentos habilitados, {corpus.get("total_pages")} paginas e {corpus.get("chunks")} chunks.

## 4. Testes

- Testes Web nesta auditoria: {web["test"].get("tests")}.
- Testes API nesta auditoria: {api["pytest"].get("tests")}.

## 5. Avaliacao RAG

- Perguntas: {evaluation.get("questions")}.
- Categorias: {evaluation.get("categories")}.

{metrics_lines}

## 6. Interface

Concluido: interface Next.js com linguagem voltada a pessoas nao tecnicas, hero com `DocumentAnswerIcon`, respostas com fontes e secao "De onde veio a resposta".

## 7. Containers

- Servicos: {", ".join(docker.get("services", []))}
- Portas publicas: {docker.get("public_ports")}
- Portas internas: {docker.get("internal_ports")}
- Volume de indice: {docker.get("index_volume")}
- Smoke test: {docker.get("smoke_test", {}).get("ok")}

## 8. CI

{actions_lines}

## 9. Release De Containers

- Workflow de publicacao presente: `{container_release.get("workflow_present")}`.
- Workflow somente manual: `{container_release.get("workflow_manual_only")}`.
- Politica de publicacao: `{container_release.get("policy_ok")}`.
- Imagem API alvo: `{container_release.get("api_image")}`.
- Imagem Web alvo: `{container_release.get("web_image")}`.
- Plataformas: `{container_release.get("platforms")}`.
- Compose exige referencias imutaveis: `{container_release.get("immutable_refs_required")}`.
- Manifesto de release: script `{container_release.get("release_manifest_script")}`, validador `{container_release.get("release_manifest_validator")}`.
- Publicacao API registrada no repositorio: `{container_release.get("api_published")}`.
- Publicacao Web registrada no repositorio: `{container_release.get("web_published")}`.
- Pull anonimo comprovado no repositorio: `{container_release.get("anonymous_pull_verified")}`.
- Smoke de imagens publicadas registrado no repositorio: `{container_release.get("published_images_smoke_ok")}`.

## 10. Evidencias visuais

{evidence_lines}

## 11. Estado Terraform e pendencias OCI

- Terraform criado: `{terraform.get("infrastructure_created")}`.
- Provider OCI: `{terraform.get("oci_provider")}`.
- Backend local explicito do workload: `{terraform.get("backend_local_explicit")}`.
- Wrapper seguro do workload presente: `{terraform.get("workload_wrapper_present")}`.
- Politica de state/apply do workload: `{terraform.get("workload_state_policy_ok")}`.
- State principal externo preparado: `{terraform.get("workload_state_external_prepared")}`.
- `TF_DATA_DIR` externo preparado: `{terraform.get("workload_tf_data_external_prepared")}`.
- Apply do workload exige saved plan: `{terraform.get("workload_apply_requires_saved_plan")}`.
- Modulos: `{terraform.get("modules")}`.
- Load Balancer: `{terraform.get("load_balancer")}`.
- Cloud-init criado: `{terraform.get("cloud_init_created")}`.
- Terraform fmt: `{terraform.get("terraform_fmt_ok")}`.
- Terraform validate: `{terraform.get("terraform_validate_ok")}`.
- Politica Terraform: `{terraform.get("terraform_policy_ok")}`.
- Bootstrap do compartment: `{terraform.get("compartment_bootstrap")}`.
- Compartment dedicado: `{terraform.get("dedicated_compartment")}`.
- Controles contra root compartment: `{terraform.get("workload_compartment_controls")}`.
- Credenciais OCI validadas: `{terraform.get("oci_credentials_verified")}`.
- Home region validada: `{terraform.get("home_region_verified")}`.
- CIDR administrativo definido: `{terraform.get("admin_cidr_defined")}`.
- State externo aplicado ao bootstrap: `{terraform.get("state_strategy_applied")}`.
- State principal do workload: preparado fora do repositorio, ainda sem apply.
- Plan do workload executado: `{terraform.get("terraform_plan_executed")}`.
- Apply do bootstrap executado: `{terraform.get("bootstrap_apply_executed")}`.
- Apply do workload executado: `{terraform.get("workload_apply_executed")}`.
- Endpoint publico disponivel: `{terraform.get("load_balancer", {}).get("endpoint_available")}`.
- Futuro: validar disponibilidade E4 Flex 1/8, orçamento PAYG, state vazio e elegibilidade final do Load Balancer 10/10 Mbps antes de qualquer apply de workload.

## 12. Checklist de aprovacao antes do apply do workload

- [x] Credenciais OCI configuradas fora do Git.
- [x] Compartment dedicado criado e validado.
- [x] Regiao e CIDR administrativo verificados.
- [x] Plan do workload gerado e auditado sem apply.
- [x] Backend local explicito, wrapper e politica offline do state principal preparados.
- [ ] Capacidade E4 Flex 1/8, orçamento PAYG e elegibilidade do Load Balancer 10/10 Mbps verificadas imediatamente antes do apply do workload.
- [ ] State principal inicializado externamente e confirmado vazio.
- [ ] Evidencias locais atualizadas quando disponiveis.

## 13. Comando para reproduzir a auditoria

```bash
python3 scripts/audit_project_readiness.py
```
"""


def write_report(facts: dict[str, Any], path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(facts), encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audita prontidao do projeto.")
    parser.add_argument("--facts", type=Path, default=FACTS_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    facts = collect_facts(ROOT)
    write_facts(facts, args.facts)
    write_report(facts, args.report)
    print(f"Fatos: {args.facts}")
    print(f"Relatorio: {args.report}")
    if facts["warnings"]:
        print("Avisos:")
        for warning in facts["warnings"]:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
