from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VALID_DIGEST_A = "sha256:" + "a" * 64
VALID_DIGEST_B = "sha256:" + "b" * 64
VALID_COMMIT = "c" * 40


def load_script(name: str):
    script_path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": "brodyandre/edudocs-ai-agent-oci",
        "source_commit": VALID_COMMIT,
        "created_at": "2026-07-27T12:00:00Z",
        "workflow_run": "123456",
        "platforms": ["linux/amd64", "linux/arm64"],
        "api": {
            "image": "ghcr.io/brodyandre/edudocs-ai-api",
            "digest": VALID_DIGEST_A,
            "immutable_ref": f"ghcr.io/brodyandre/edudocs-ai-api@{VALID_DIGEST_A}",
        },
        "web": {
            "image": "ghcr.io/brodyandre/edudocs-ai-web",
            "digest": VALID_DIGEST_B,
            "immutable_ref": f"ghcr.io/brodyandre/edudocs-ai-web@{VALID_DIGEST_B}",
        },
        "runtime": {
            "public_entry_port": 80,
            "load_balancer_backend_port": 8080,
            "health_path": "/health",
        },
    }


def kinds(manifest: dict[str, object]) -> set[str]:
    checker = load_script("check_container_release_manifest")
    return {finding.kind for finding in checker.validate_manifest(manifest)}


def test_valid_manifest_is_accepted() -> None:
    checker = load_script("check_container_release_manifest")

    assert checker.validate_manifest(valid_manifest()) == []


def test_invalid_commit_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["source_commit"] = "abc"

    assert "invalid-commit" in kinds(manifest)


def test_invalid_digest_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["api"]["digest"] = "sha256:xyz"  # type: ignore[index]

    assert "invalid-digest" in kinds(manifest)


def test_missing_arm64_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["platforms"] = ["linux/amd64"]

    assert "invalid-platforms" in kinds(manifest)


def test_missing_amd64_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["platforms"] = ["linux/arm64"]

    assert "invalid-platforms" in kinds(manifest)


def test_unexpected_image_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["web"]["image"] = "ghcr.io/brodyandre/other"  # type: ignore[index]

    assert "unexpected-image" in kinds(manifest)


def test_latest_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["api"]["immutable_ref"] = "ghcr.io/brodyandre/edudocs-ai-api:latest"  # type: ignore[index]

    assert "latest-reference" in kinds(manifest)


def test_backend_port_must_be_8080() -> None:
    manifest = valid_manifest()
    manifest["runtime"]["load_balancer_backend_port"] = 8000  # type: ignore[index]

    assert "invalid-runtime" in kinds(manifest)


def test_health_path_must_be_health() -> None:
    manifest = valid_manifest()
    manifest["runtime"]["health_path"] = "/ready"  # type: ignore[index]

    assert "invalid-runtime" in kinds(manifest)


def test_token_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["workflow_run"] = "ghp_" + "123456789012345678901234"

    assert "sensitive-content" in kinds(manifest)


def test_private_key_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["created_at"] = "-----BEGIN " + "PRIVATE KEY-----"

    assert "sensitive-content" in kinds(manifest)


def test_ocid_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["workflow_run"] = "ocid1." + "compartment.oc1..aaaa"

    assert "sensitive-content" in kinds(manifest)


def test_ip_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["workflow_run"] = "203.0.113.10"

    assert "ip-address" in kinds(manifest)


def test_generator_is_idempotent(tmp_path: Path) -> None:
    generator = load_script("generate_container_release_manifest")

    args = type(
        "Args",
        (),
        {
            "commit": VALID_COMMIT,
            "api_image": "ghcr.io/brodyandre/edudocs-ai-api",
            "api_digest": VALID_DIGEST_A,
            "web_image": "ghcr.io/brodyandre/edudocs-ai-web",
            "web_digest": VALID_DIGEST_B,
            "created_at": "2026-07-27T12:00:00Z",
            "workflow_run": "123456",
            "repository": "brodyandre/edudocs-ai-agent-oci",
            "output": tmp_path / "manifest.json",
        },
    )

    first = generator.build_manifest(args)
    second = generator.build_manifest(args)

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
