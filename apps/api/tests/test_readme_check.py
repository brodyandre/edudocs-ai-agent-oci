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


def valid_readme_text() -> str:
    markers = "\n".join(
        f"<!-- EVIDENCE:{key}:START -->\n"
        "> **Captura pendente:** `docs/evidence/x.png`.\n"
        f"<!-- EVIDENCE:{key}:END -->"
        for key in (
            "HOME",
            "ANSWER",
            "UNSUPPORTED",
            "DOCUMENTS",
            "ACTIONS",
            "DOCKER",
            "OCI_APP",
            "OCI_INSTANCE",
        )
    )
    return f"""# EduDocs AI

## Índice

- [Demonstração da experiência](#demonstração-da-experiência)
- [Problema resolvido](#problema-resolvido)
- [Como funciona](#como-funciona)
- [Como o agente responde](#como-o-agente-responde)
- [Quando a informação não existe](#quando-a-informação-não-existe)
- [Documentos disponíveis](#documentos-disponíveis)
- [Experiência para pessoas não técnicas](#experiência-para-pessoas-não-técnicas)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Qualidade e avaliação](#qualidade-e-avaliação)

## Demonstração da experiência

{markers}

[Voltar ao índice](#índice)

## Problema resolvido

Texto.

## Como funciona
Texto.

## Como o agente responde
Texto.

## Quando a informação não existe
Texto.

## Documentos disponíveis
Texto.

## Experiência para pessoas não técnicas
Texto.

## Arquitetura
Texto.

## Tecnologias
Texto.

## Qualidade e avaliação
Texto.
"""


def test_check_readme_accepts_valid_structure(tmp_path: Path) -> None:
    check = load_script("check_readme")

    findings = check.validate_readme(valid_readme_text(), tmp_path)

    assert findings == []


def test_check_readme_flags_absolute_path() -> None:
    check = load_script("check_readme")

    findings = check.validate_readme(valid_readme_text() + "\n/home/luizandre/x\n")

    assert any(finding.kind == "absolute-path" for finding in findings)


def test_check_readme_flags_missing_anchor() -> None:
    check = load_script("check_readme")

    findings = check.validate_readme(valid_readme_text() + "\n[Quebrado](#nao-existe)\n")

    assert any(finding.kind == "broken-anchor" for finding in findings)
