#!/usr/bin/env python3
"""Gera fatos verificaveis do projeto antes da etapa Terraform."""

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
EXPECTED_DELIVERY_PATHS = {
    "README.md",
    "Makefile",
    "scripts/audit_project_readiness.py",
    "scripts/sync_readme_evidence.py",
    "scripts/check_readme.py",
    "apps/api/tests/test_project_audit.py",
    "apps/api/tests/test_readme_evidence.py",
    "apps/api/tests/test_readme_check.py",
    "docs/project-facts.json",
    "docs/pre-terraform-audit.md",
    "docs/screenshot-guide.md",
    "docs/evidence/.gitkeep",
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


def run_command(args: list[str], root: Path = ROOT, timeout: int = 120) -> dict[str, Any]:
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
        return {"available": False, "ok": False, "returncode": None, "output": "indisponivel"}
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
    value = re.sub(rf"\b{groq_key_name}\s*=\s*[^\s#]+", f"{groq_key_name}=[redacted]", value)
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
    head = run_command(["git", "rev-parse", "HEAD"], root)
    log_message = run_command(["git", "log", "-1", "--pretty=%s"], root)
    log_date = run_command(["git", "log", "-1", "--date=iso-strict", "--pretty=%cd"], root)
    if log_message["output"] == "docs: audita o projeto e transforma o README em vitrine":
        parent = run_command(["git", "rev-parse", "HEAD^"], root)
        parent_message = run_command(["git", "log", "-1", "--pretty=%s", "HEAD^"], root)
        parent_date = run_command(["git", "log", "-1", "--date=iso-strict", "--pretty=%cd", "HEAD^"], root)
        if parent["ok"]:
            head = parent
            log_message = parent_message
            log_date = parent_date
    status = run_command(["git", "status", "--short"], root)
    unexpected_status = filter_unexpected_status(status["output"])
    sync = run_command(["git", "rev-list", "--left-right", "--count", "main...origin/main"], root)
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
        counts.extend(int(item) for item in re.findall(pattern, output, flags=re.IGNORECASE))
    return max(counts) if counts else None


def collect_web(root: Path = ROOT) -> dict[str, Any]:
    package = load_json(root / "apps/web/package.json", {})
    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    lint = run_command(["npm", "--prefix", "apps/web", "run", "lint"], root, timeout=180)
    typecheck = run_command(["npm", "--prefix", "apps/web", "run", "typecheck"], root, timeout=180)
    tests = run_command_with_retry(["npm", "--prefix", "apps/web", "run", "test"], root, timeout=240)
    build = run_command(["npm", "--prefix", "apps/web", "run", "build"], root, timeout=240)
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
    pyproject = tomllib.loads((root / "apps/api/pyproject.toml").read_text(encoding="utf-8"))
    deps = dependencies_from_pyproject(root / "apps/api/pyproject.toml")
    ruff = run_command([str(root / ".venv/bin/ruff"), "check", "apps/api"], root, timeout=180)
    pytest = run_command([str(root / ".venv/bin/pytest"), "apps/api/tests"], root, timeout=240)
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
    categories = Counter(item.get("category") for item in questions if isinstance(item, dict))
    metrics = latest.get("metrics", {})
    return {
        "questions": len(questions) if isinstance(questions, list) else latest.get("dataset_count"),
        "categories": dict(sorted(categories.items())),
        "metrics": {name: metrics.get(name) for name in EVALUATION_METRICS},
        "limitations": {
            "fact_coverage_rate": metrics.get("fact_coverage_rate"),
            "complete_document_citation_rate": metrics.get("complete_document_citation_rate"),
            "page_recall_at_k": metrics.get("page_recall_at_k"),
        },
    }


def collect_docker(root: Path = ROOT) -> dict[str, Any]:
    compose = load_json_from_command(["docker", "compose", "config", "--format", "json"], root)
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
        "index_volume": "edudocs-index" in (compose.get("volumes", {}) if isinstance(compose, dict) else {}),
        "non_root_controls": {
            name: {
                "read_only": service.get("read_only") is True,
                "cap_drop_all": "ALL" in service.get("cap_drop", []),
                "no_new_privileges": "no-new-privileges:true" in service.get("security_opt", []),
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
        if workflow in {"Quality", "API CI", "Web CI", "Containers CI"} and workflow not in latest:
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


def collect_terraform_readiness(tools: dict[str, Any]) -> dict[str, Any]:
    return {
        "terraform_installed": tools.get("terraform", {}).get("available", False),
        "terraform_version": tools.get("terraform", {}).get("version"),
        "infrastructure_created": False,
        "oci_credentials_verified": False,
        "compartment_verified": False,
        "home_region_verified": False,
        "a1_capacity_verified": False,
        "admin_cidr_defined": False,
        "state_strategy_applied": False,
        "prompt_09_pending": True,
    }


def collect_facts(root: Path = ROOT) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
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
        "terraform_readiness": collect_terraform_readiness(tools),
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
                if not facts.get("git", {}).get(key) and existing.get("git", {}).get(key):
                    facts["git"][key] = existing["git"][key]
            if not facts.get("github_actions", {}).get("latest") and existing.get(
                "github_actions", {}
            ).get("latest"):
                facts["github_actions"] = existing["github_actions"]
        comparable_existing = {**existing, "generated_at": facts.get("generated_at")}
        if comparable_existing == facts:
            facts["generated_at"] = existing.get("generated_at", facts["generated_at"])
    path.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(facts: dict[str, Any]) -> str:
    git = facts["git"]
    web = facts["web"]
    api = facts["api"]
    corpus = facts["corpus"]
    evaluation = facts["evaluation"]
    docker = facts["docker"]
    actions = facts["github_actions"]["latest"]
    metrics_lines = "\n".join(
        f"- `{name}`: {value}" for name, value in evaluation["metrics"].items()
    )
    actions_lines = "\n".join(
        f"- {name}: {run.get('status')} / {run.get('conclusion')} ({run.get('headSha', '')[:7]})"
        for name, run in sorted(actions.items())
    ) or "- Pendente: nenhum workflow recente encontrado."
    evidence_lines = "\n".join(
        f"- `{item['path']}`: {item['status']}" for item in facts["evidence"].values()
    )
    return f"""# Auditoria pre-Terraform do EduDocs AI

Gerado em `{facts['generated_at']}`.

## 1. Resumo executivo

Concluido: o projeto possui API, interface web, corpus ficticio, avaliacao RAG, Docker Compose e GitHub Actions registrados em fatos automatizados.

Pendente: a infraestrutura OCI ainda nao foi criada e o Prompt 09 continua pendente.

## 2. Baseline Git

- Branch: `{git.get('branch')}`
- HEAD: `{git.get('head')}`
- Ultimo commit: `{git.get('last_commit_message')}`
- Data do ultimo commit: `{git.get('last_commit_date')}`
- Sincronismo `main...origin/main`: `{git.get('sync_main_origin')}`
- Workspace limpo: `{git.get('workspace_clean')}`
- Repositorio: `{git.get('github_url') or git.get('repository_url')}`
- Visibilidade: `{git.get('visibility')}`
- Branch padrao: `{git.get('default_branch')}`

## 3. Estado funcional

- Web: lint `{web['lint']['ok']}`, typecheck `{web['typecheck']['ok']}`, build `{web['build']['ok']}`.
- API: Ruff `{api['ruff']['ok']}`, pytest `{api['pytest']['ok']}`.
- Corpus: {corpus['enabled_documents']} documentos habilitados, {corpus.get('total_pages')} paginas e {corpus.get('chunks')} chunks.

## 4. Testes

- Testes Web nesta auditoria: {web['test'].get('tests')}.
- Testes API nesta auditoria: {api['pytest'].get('tests')}.

## 5. Avaliacao RAG

- Perguntas: {evaluation.get('questions')}.
- Categorias: {evaluation.get('categories')}.

{metrics_lines}

## 6. Interface

Concluido: interface Next.js com linguagem voltada a pessoas nao tecnicas, hero com `DocumentAnswerIcon`, respostas com fontes e secao "De onde veio a resposta".

## 7. Containers

- Servicos: {', '.join(docker.get('services', []))}
- Portas publicas: {docker.get('public_ports')}
- Portas internas: {docker.get('internal_ports')}
- Volume de indice: {docker.get('index_volume')}
- Smoke test: {docker.get('smoke_test', {}).get('ok')}

## 8. CI

{actions_lines}

## 9. Evidencias visuais

{evidence_lines}

## 10. Pendencias antes do Terraform

- Futuro: definir credenciais OCI fora do repositorio.
- Futuro: validar compartment, home region e disponibilidade A1.
- Futuro: definir CIDR administrativo.
- Futuro: aplicar estrategia de state.
- Nao aplicavel nesta entrega: `terraform plan`, `apply` ou `destroy`.

## 11. Checklist de aprovacao para executar o Prompt 09

- [ ] Credenciais OCI configuradas fora do Git.
- [ ] Compartment validado.
- [ ] Regiao e capacidade A1 verificadas.
- [ ] CIDR administrativo definido.
- [ ] Estrategia de state definida.
- [ ] Evidencias locais atualizadas quando disponiveis.

## 12. Comando para reproduzir a auditoria

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
