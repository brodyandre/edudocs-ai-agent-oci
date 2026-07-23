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


def readme_with_markers() -> str:
    sync = load_script("sync_readme_evidence")
    parts = ["# README\n"]
    for block in sync.EVIDENCE_BLOCKS:
        parts.append(f"{block.start}\nmanual\n{block.end}\n")
    return "\n".join(parts)


def test_sync_is_idempotent_and_avoids_broken_image_links(tmp_path: Path) -> None:
    sync = load_script("sync_readme_evidence")
    readme = tmp_path / "README.md"
    readme.write_text(readme_with_markers(), encoding="utf-8")

    assert sync.sync_readme(readme, tmp_path) is True
    first = readme.read_text(encoding="utf-8")
    assert sync.sync_readme(readme, tmp_path) is False
    assert readme.read_text(encoding="utf-8") == first
    assert "![Hero" not in first
    assert "Captura pendente" in first


def test_sync_inserts_existing_evidence(tmp_path: Path) -> None:
    sync = load_script("sync_readme_evidence")
    readme = tmp_path / "README.md"
    (tmp_path / "docs/evidence").mkdir(parents=True)
    (tmp_path / "docs/evidence/home-hero.png").write_bytes(b"png")
    readme.write_text(readme_with_markers(), encoding="utf-8")

    sync.sync_readme(readme, tmp_path)

    text = readme.read_text(encoding="utf-8")
    assert "![Hero da interface de consulta documental.](docs/evidence/home-hero.png)" in text


def test_sync_fails_on_missing_marker(tmp_path: Path) -> None:
    sync = load_script("sync_readme_evidence")
    readme = tmp_path / "README.md"
    readme.write_text("# README\n", encoding="utf-8")

    try:
        sync.sync_readme(readme, tmp_path)
    except ValueError as exc:
        assert "Marcadores invalidos" in str(exc)
    else:
        raise AssertionError("sync_readme deveria falhar sem marcadores")


def test_sync_fails_on_duplicate_marker(tmp_path: Path) -> None:
    sync = load_script("sync_readme_evidence")
    readme = tmp_path / "README.md"
    text = readme_with_markers().replace(
        "<!-- EVIDENCE:HOME:START -->",
        "<!-- EVIDENCE:HOME:START -->\n<!-- EVIDENCE:HOME:START -->",
    )
    readme.write_text(text, encoding="utf-8")

    try:
        sync.sync_readme(readme, tmp_path)
    except ValueError as exc:
        assert "HOME" in str(exc)
    else:
        raise AssertionError("sync_readme deveria falhar com marcador duplicado")
