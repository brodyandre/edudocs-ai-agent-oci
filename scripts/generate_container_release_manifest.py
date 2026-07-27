#!/usr/bin/env python3
"""Gera o manifesto JSON sanitizado das imagens multiarch publicadas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_container_release_manifest import validate_manifest


PLATFORMS = ["linux/amd64", "linux/arm64"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera manifesto de release de containers.")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--web-digest", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def build_manifest(args: argparse.Namespace) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": args.repository,
        "source_commit": args.commit,
        "created_at": args.created_at,
        "workflow_run": str(args.workflow_run),
        "platforms": PLATFORMS,
        "api": {
            "image": args.api_image,
            "digest": args.api_digest,
            "immutable_ref": f"{args.api_image}@{args.api_digest}",
        },
        "web": {
            "image": args.web_image,
            "digest": args.web_digest,
            "immutable_ref": f"{args.web_image}@{args.web_digest}",
        },
        "runtime": {
            "public_entry_port": 80,
            "load_balancer_backend_port": 8080,
            "health_path": "/health",
        },
    }


def main() -> int:
    args = build_parser().parse_args()
    manifest = build_manifest(args)
    findings = validate_manifest(manifest)
    if findings:
        for finding in findings:
            print(f"{finding.path}: {finding.kind}: {finding.guidance}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Manifesto: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
