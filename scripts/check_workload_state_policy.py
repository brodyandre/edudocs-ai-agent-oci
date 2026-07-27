#!/usr/bin/env python3
"""Valida politica de state externo e apply controlado do workload OCI."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_DIR = ROOT / "infrastructure" / "terraform"
WRAPPER = ROOT / "scripts" / "terraform_workload.sh"
EXPECTED_STATE_DIR = "$HOME/.local/state/edudocs/workload"
EXPECTED_STATE_PATH = "$HOME/.local/state/edudocs/workload/terraform.tfstate"
EXPECTED_TF_DATA_DIR = "$HOME/.local/share/edudocs/terraform-workload"


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def workflow_files(root: Path) -> list[Path]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    return sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")])


def tracked_or_existing_files(root: Path) -> list[str]:
    if (root / ".git").is_dir():
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            text=False,
        )
        return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".terraform" not in path.parts
    ]


def terraform_backend_block(text: str) -> str | None:
    match = re.search(r'backend\s+"local"\s*\{(?P<body>.*?)\}', text, flags=re.DOTALL)
    return match.group("body") if match else None


def check_backend(root: Path) -> list[Finding]:
    versions = root / "infrastructure" / "terraform" / "versions.tf"
    findings: list[Finding] = []
    if not versions.is_file():
        return [Finding(rel(versions, root), "missing-versions", "versions.tf ausente.")]
    text = read_text(versions)
    block = terraform_backend_block(text)
    if block is None:
        findings.append(
            Finding(rel(versions, root), "backend-missing", 'Backend "local" ausente.')
        )
        return findings
    if re.search(r"\bpath\s*=", block):
        findings.append(
            Finding(
                rel(versions, root),
                "backend-path-versioned",
                "Caminho de state nao pode ser versionado.",
            )
        )
    if re.search(r"\b(access_key|secret_key|fingerprint|private_key|user_ocid)\b", block):
        findings.append(
            Finding(rel(versions, root), "backend-credential", "Backend contem credencial.")
        )
    return findings


def check_wrapper(root: Path) -> list[Finding]:
    wrapper = root / "scripts" / "terraform_workload.sh"
    findings: list[Finding] = []
    if not wrapper.is_file():
        return [Finding(rel(wrapper, root), "wrapper-missing", "Wrapper ausente.")]
    text = read_text(wrapper)
    rel_path = rel(wrapper, root)
    required = {
        "bash-strict-mode": "set -euo pipefail",
        "umask-077": "umask 077",
        "home-required": '[[ -z "${HOME:-}" ]]',
        "state-dir-default": ".local/state/edudocs/workload",
        "state-path-default": "terraform.tfstate",
        "tf-data-default": ".local/share/edudocs/terraform-workload",
        "tf-data-export": 'export TF_DATA_DIR="$WORKLOAD_TF_DATA_DIR"',
        "repo-refusal": "dentro do repositorio",
        "init-reconfigure": "-reconfigure",
        "init-input-false": "-input=false",
        "backend-config-path": "-backend-config=\"path=$WORKLOAD_STATE_PATH\"",
        "plan-out": "-out=\"$planfile\"",
        "plan-input-false": "-input=false",
        "apply-saved-plan-command": "apply-saved-plan)",
        "apply-input-false": "apply -input=false \"$1\"",
        "post-apply-detailed-exitcode": "-detailed-exitcode",
    }
    for kind, needle in required.items():
        if needle not in text:
            findings.append(Finding(rel_path, kind, "Contrato obrigatorio ausente."))

    forbidden_tokens = {
        "destroy-command": r"\bdestroy\)",
        "import-command": r"\bimport\)",
        "terraform-import-command": r"terraform\s+import\b",
        "state-rm-command": r"state-rm|state rm",
        "state-mv-command": r"state-mv|state mv",
        "state-push-command": r"state-push|state push",
        "taint-command": r"\btaint\)",
        "force-unlock-command": r"force-unlock",
        "auto-approve": r"terraform[^\n]*-auto-approve",
        "target": r"terraform[^\n]*\s-target",
        "refresh-false": r"terraform[^\n]*refresh=false",
        "eval-arbitrary": r"\beval\b",
        "exec-arbitrary": r"\bexec\s+\"\$@\"",
    }
    for kind, pattern in forbidden_tokens.items():
        if re.search(pattern, text):
            findings.append(Finding(rel_path, kind, "Wrapper contem operacao proibida."))

    if re.search(r"terraform\s+-chdir=.*\sapply\b", text) and (
        "apply -input=false \"$1\"" not in text
        or "require_tmp_plan \"$1\"" not in text
    ):
        findings.append(
            Finding(
                rel_path,
                "apply-without-saved-plan",
                "Apply deve ocorrer somente com plan salvo validado.",
            )
        )
    if "/tmp/*.tfplan" not in text:
        findings.append(
            Finding(
                rel_path,
                "apply-plan-not-tmp",
                "Apply deve exigir planfile em /tmp.",
            )
        )
    if "stat -c '%a'" not in text or '[[ "$mode" != "600" ]]' not in text:
        findings.append(
            Finding(rel_path, "plan-permission-check", "Planfile deve exigir permissao 600.")
        )
    return findings


def check_ci_and_makefile(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    makefile = root / "Makefile"
    if makefile.is_file():
        text = read_text(makefile)
        if re.search(r"^apply\s*:", text, flags=re.MULTILINE):
            findings.append(
                Finding("Makefile", "make-apply-target", "Makefile nao pode criar target apply.")
            )
        for pattern, kind in {
            r"\bterraform\s+apply\b": "make-terraform-apply",
            r"\bterraform\s+destroy\b": "make-terraform-destroy",
            r"\bscripts/terraform_workload\.sh\s+apply-saved-plan\b": "make-wrapper-apply",
            r"-auto-approve": "make-auto-approve",
            r"\s-target": "make-target",
            r"refresh=false": "make-refresh-false",
        }.items():
            if re.search(pattern, text):
                findings.append(
                    Finding("Makefile", kind, "Makefile contem operacao proibida.")
                )
    for path in workflow_files(root):
        text = read_text(path)
        rel_path = rel(path, root)
        for pattern, kind in {
            r"\bterraform\s+apply\b": "workflow-terraform-apply",
            r"\bterraform\s+destroy\b": "workflow-terraform-destroy",
            r"\bscripts/terraform_workload\.sh\s+apply-saved-plan\b": "workflow-wrapper-apply",
            r"\bterraform\s+import\b": "workflow-import",
            r"-auto-approve": "workflow-auto-approve",
            r"\s-target": "workflow-target",
            r"refresh=false": "workflow-refresh-false",
            r"id-token:\s*write|contents:\s*write": "workflow-permission",
        }.items():
            if re.search(pattern, text):
                findings.append(
                    Finding(rel_path, kind, "Workflow contem operacao proibida.")
                )
    return findings


def check_sensitive_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_or_existing_files(root):
        name = Path(path).name
        if path.endswith("terraform.tfvars.example"):
            continue
        if name == "terraform.tfvars" or name == "runtime.env":
            findings.append(
                Finding(path, "forbidden-versioned-file", "Nao versione tfvars/runtime reais.")
            )
        if name.endswith((".tfstate", ".tfstate.backup", ".tfplan", ".pem", ".key")):
            findings.append(
                Finding(path, "forbidden-versioned-file", "Nao versione state, plan ou chave.")
            )
    return findings


def check_secret_text(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    allowed_ocids = {
        "ocid1." + "tenancy.oc1..substitua",
        "ocid1." + "compartment.oc1..substitua",
        "ocid1." + "image.oc1..substitua",
    }
    candidates = [
        path
        for path in [
            root / "scripts" / "terraform_workload.sh",
            root / "Makefile",
            *workflow_files(root),
            root / "infrastructure" / "terraform" / "versions.tf",
        ]
        if path.is_file()
    ]
    for path in candidates:
        text = read_text(path)
        rel_path = rel(path, root)
        for pattern, kind in {
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----": "private-key",
            r"\b(?:fingerprint|private_key|user_ocid)\b": "credential-word",
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b": "github-token",
            r"\bgithub_pat_[A-Za-z0-9_]{20,}\b": "github-pat",
            r"\bEDUDOCS_ADMIN_CIDR\s*=": "admin-cidr-value",
        }.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                findings.append(Finding(rel_path, kind, "Conteudo sensivel proibido."))
        for ocid in re.findall(r"ocid1\.[A-Za-z0-9_.-]+", text):
            if ocid not in allowed_ocids:
                findings.append(
                    Finding(rel_path, "real-ocid-risk", "OCID real nao pode ser versionado.")
                )
    return findings


def collect_findings(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_backend(root))
    findings.extend(check_wrapper(root))
    findings.extend(check_ci_and_makefile(root))
    findings.extend(check_sensitive_files(root))
    findings.extend(check_secret_text(root))
    return findings


def main() -> int:
    findings = collect_findings(ROOT)
    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.kind}: {finding.message}")
        return 1
    print("OK: politica de state/apply do workload validada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
