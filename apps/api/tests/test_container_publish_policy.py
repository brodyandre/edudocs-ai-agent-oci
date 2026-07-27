from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_policy():
    script_path = ROOT / "scripts" / "check_container_publish_policy.py"
    spec = importlib.util.spec_from_file_location("check_container_publish_policy", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_container_publish_policy"] = module
    spec.loader.exec_module(module)
    return module


def valid_workflow() -> str:
    return """
name: Publish Images
on:
  workflow_dispatch:
    inputs:
      publish_main_alias:
        type: boolean
        default: true
permissions:
  contents: read
  packages: write
concurrency:
  group: publish-images-${{ github.ref }}
  cancel-in-progress: false
jobs:
  publish:
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/metadata-action@v5
        with:
          images: ghcr.io/brodyandre/edudocs-ai-api
          tags: type=raw,value=sha-${{ github.sha }}
          labels: org.opencontainers.image.revision=${{ github.sha }}
      - uses: docker/metadata-action@v5
        with:
          images: ghcr.io/brodyandre/edudocs-ai-web
          tags: type=raw,value=sha-${{ github.sha }}
          labels: org.opencontainers.image.source=https://github.com/brodyandre/edudocs-ai-agent-oci
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/api/Dockerfile
          platforms: linux/amd64,linux/arm64
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/web/Dockerfile
          platforms: linux/amd64,linux/arm64
      - run: |
          API_DIGEST="${{ steps.build-api.outputs.digest }}"
          WEB_DIGEST="${{ steps.build-web.outputs.digest }}"
          API_REF="${API_IMAGE}@${API_DIGEST}"
          WEB_REF="${WEB_IMAGE}@${WEB_DIGEST}"
          echo "@${API_DIGEST} @${WEB_DIGEST}"
          echo "@${API_DIGEST}" | sed "s/@${API_DIGEST}/@${API_DIGEST}/"
          echo "@${WEB_DIGEST}" | sed "s/@${WEB_DIGEST}/@${WEB_DIGEST}/"
          ANON_DOCKER_CONFIG="$(mktemp -d)"
          DOCKER_CONFIG="$ANON_DOCKER_CONFIG" docker buildx imagetools inspect "$API_REF"
          docker compose -f docker-compose.prod.yml up -d
          python3 scripts/smoke_test.py
"""


def valid_compose() -> str:
    return """
services:
  api:
    image: "${API_IMAGE_REF:?Defina API_IMAGE_REF com digest imutavel sha256}"
    expose:
      - "8000"
  web:
    image: "${WEB_IMAGE_REF:?Defina WEB_IMAGE_REF com digest imutavel sha256}"
    expose:
      - "3000"
  nginx:
    image: nginxinc/nginx-unprivileged:1.27.4-alpine
    ports:
      - "${NGINX_PORT:-8080}:8080"
"""


def write_tree(root: Path, workflow: str | None = None, compose: str | None = None) -> None:
    workflow_path = root / ".github/workflows/publish-images.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text((workflow or valid_workflow()).strip() + "\n", encoding="utf-8")
    compose_path = root / "docker-compose.prod.yml"
    compose_path.write_text((compose or valid_compose()).strip() + "\n", encoding="utf-8")
    other = root / ".github/workflows/quality.yml"
    other.write_text("permissions:\n  contents: read\n", encoding="utf-8")


def kinds(root: Path) -> set[str]:
    policy = load_policy()
    return {finding.kind for finding in policy.collect_findings(root)}


def test_valid_workflow_is_accepted(tmp_path: Path) -> None:
    policy = load_policy()
    write_tree(tmp_path)

    assert policy.collect_findings(tmp_path) == []


def test_pull_request_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("workflow_dispatch:", "pull_request:"))

    assert "forbidden-trigger" in kinds(tmp_path)


def test_pull_request_target_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("workflow_dispatch:", "pull_request_target:"))

    assert "forbidden-trigger" in kinds(tmp_path)


def test_contents_write_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("contents: read", "contents: write"))

    assert "excessive-permission" in kinds(tmp_path)


def test_pat_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("secrets.GITHUB_TOKEN", "secrets.GHCR_TOKEN"))

    assert "pat-reference" in kinds(tmp_path)


def test_latest_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("sha-${{ github.sha }}", "latest"))

    assert "latest-reference" in kinds(tmp_path)


def test_missing_arm64_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("linux/amd64,linux/arm64", "linux/amd64"))

    assert "missing-platforms" in kinds(tmp_path)


def test_missing_amd64_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("linux/amd64,linux/arm64", "linux/arm64"))

    assert "missing-platforms" in kinds(tmp_path)


def test_unexpected_image_is_rejected(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        valid_workflow().replace(
            "ghcr.io/brodyandre/edudocs-ai-web", "ghcr.io/brodyandre/other"
        ),
    )

    assert "unexpected-image" in kinds(tmp_path)


def test_missing_github_token_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("secrets.GITHUB_TOKEN", "github.actor"))

    assert "missing-github-token-login" in kinds(tmp_path)


def test_missing_packages_write_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("packages: write", "packages: read"))

    assert "missing-packages-write" in kinds(tmp_path)


def test_missing_anonymous_verification_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("ANON_DOCKER_CONFIG", "DOCKER_CONFIG_DIR"))

    assert "missing-anonymous-inspect" in kinds(tmp_path)


def test_missing_smoke_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("python3 scripts/smoke_test.py", "echo ok"))

    assert "missing-smoke" in kinds(tmp_path)


def test_missing_timeout_is_rejected(tmp_path: Path) -> None:
    write_tree(tmp_path, valid_workflow().replace("timeout-minutes: 60", ""))

    assert "missing-timeout" in kinds(tmp_path)


def test_missing_concurrency_is_rejected(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        valid_workflow().replace("group: publish-images-${{ github.ref }}", "group: x"),
    )

    assert "missing-concurrency" in kinds(tmp_path)
