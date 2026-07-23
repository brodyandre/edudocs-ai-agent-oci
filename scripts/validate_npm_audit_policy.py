from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


KNOWN_MODERATE_ADVISORY = "GHSA-qx2v-qp2m-jg93"
KNOWN_VULNERABLE_PACKAGES = {"postcss", "next"}
BLOCKING_SEVERITIES = {"high", "critical"}


@dataclass(frozen=True)
class AuditFinding:
    package: str
    severity: str
    via: tuple[str, ...]


def advisory_ids(via: Any) -> tuple[str, ...]:
    ids: list[str] = []
    if not isinstance(via, list):
        return ()
    for item in via:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            url = str(item.get("url", ""))
            if "GHSA-" in url:
                ids.append(url.rsplit("/", 1)[-1])
            source = item.get("source")
            if source:
                ids.append(str(source))
    return tuple(sorted(set(ids)))


def collect_findings(report: dict[str, Any]) -> list[AuditFinding]:
    vulnerabilities = report.get("vulnerabilities", {})
    if not isinstance(vulnerabilities, dict):
        return []
    findings: list[AuditFinding] = []
    for package, detail in vulnerabilities.items():
        if not isinstance(detail, dict):
            continue
        findings.append(
            AuditFinding(
                package=str(package),
                severity=str(detail.get("severity", "unknown")),
                via=advisory_ids(detail.get("via")),
            )
        )
    return findings


def is_known_accepted(finding: AuditFinding) -> bool:
    if finding.severity != "moderate" or finding.package not in KNOWN_VULNERABLE_PACKAGES:
        return False
    if finding.package == "postcss":
        return KNOWN_MODERATE_ADVISORY in finding.via
    if finding.package == "next":
        return "postcss" in finding.via
    return False


def validate_policy(report: dict[str, Any]) -> tuple[bool, list[str]]:
    messages: list[str] = []
    findings = collect_findings(report)
    blocked = [finding for finding in findings if finding.severity in BLOCKING_SEVERITIES]
    unexpected = [finding for finding in findings if not is_known_accepted(finding)]

    for finding in findings:
        status = "aceita" if is_known_accepted(finding) else "nao aceita"
        via = ", ".join(finding.via) if finding.via else "sem advisory identificado"
        messages.append(f"{finding.package}: {finding.severity}: {status}: via {via}")

    if blocked:
        messages.append("Falha: vulnerabilidade high/critical encontrada.")
    if unexpected:
        messages.append("Falha: vulnerabilidade fora da baseline aceita encontrada.")

    return not blocked and not unexpected, messages


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--scope", default="unknown")
    parser.add_argument("--npm-exit-code", type=int, default=0)
    args = parser.parse_args(argv[1:])

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    ok, messages = validate_policy(report)
    print(f"npm audit {args.scope}: exit_code={args.npm_exit_code}")
    if messages:
        for message in messages:
            print(message)
    else:
        print("Nenhuma vulnerabilidade reportada.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
