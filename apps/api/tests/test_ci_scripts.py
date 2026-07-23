from __future__ import annotations

import importlib.util
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


def test_hygiene_allows_env_example_and_flags_real_env() -> None:
    hygiene = load_script("check_repository_hygiene")

    findings = hygiene.detect_forbidden_paths(
        [".env.example", ".env", "apps/web/node_modules/pkg/index.js"]
    )

    assert not [finding for finding in findings if finding.path == ".env.example"]
    assert any(finding.path == ".env" and finding.kind == "forbidden-file" for finding in findings)
    assert any(finding.kind == "generated-directory" for finding in findings)


def test_hygiene_secret_finding_does_not_include_secret_value(tmp_path: Path) -> None:
    hygiene = load_script("check_repository_hygiene")
    secret_file = tmp_path / "settings.txt"
    secret_value = "gsk_" + "1234567890SECRET"
    secret_file.write_text("GROQ_" + f"API_KEY={secret_value}\n", encoding="utf-8")

    findings = hygiene.detect_secrets(["settings.txt"], tmp_path)

    assert len(findings) == 1
    assert "gsk_1234567890SECRET" not in findings[0].guidance


def test_npm_audit_policy_accepts_known_next_postcss_chain() -> None:
    audit = load_script("validate_npm_audit_policy")
    report = {
        "vulnerabilities": {
            "postcss": {
                "severity": "moderate",
                "via": [{"url": "https://github.com/advisories/GHSA-qx2v-qp2m-jg93"}],
            },
            "next": {"severity": "moderate", "via": ["postcss"]},
        }
    }

    ok, messages = audit.validate_policy(report)

    assert ok
    assert any("postcss: moderate: aceita" in message for message in messages)


def test_npm_audit_policy_blocks_high_severity() -> None:
    audit = load_script("validate_npm_audit_policy")
    report = {"vulnerabilities": {"example": {"severity": "high", "via": ["CVE-0000-0000"]}}}

    ok, messages = audit.validate_policy(report)

    assert not ok
    assert any("high/critical" in message for message in messages)


def test_compose_policy_requires_nginx_as_only_public_port() -> None:
    compose_policy = load_script("validate_compose_policy")
    compose = {
        "services": {
            "api": base_service(
                {"EDUDOCS_LLM_PROVIDER": "fake", "EDUDOCS_EMBEDDING_PROVIDER": "fake"}
            ),
            "web": base_service({}),
            "nginx": {**base_service({}), "ports": [{"published": "8080", "target": 8080}]},
        }
    }
    nginx = "location /api/ {}\nlocation = /health {}\nlocation = /ready {}\n"

    assert compose_policy.validate_compose(compose, nginx) == []

    compose["services"]["api"]["ports"] = [{"published": "8000", "target": 8000}]
    findings = compose_policy.validate_compose(compose, nginx)

    assert any(finding.kind == "internal-port-exposed" for finding in findings)


def base_service(environment: dict[str, str]) -> dict[str, object]:
    return {
        "environment": environment,
        "healthcheck": {"test": ["CMD", "true"]},
        "read_only": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
    }
