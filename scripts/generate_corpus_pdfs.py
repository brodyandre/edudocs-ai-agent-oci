#!/usr/bin/env python3
"""Gera PDFs pesquisáveis do corpus fictício da EduDocs Academy."""

from __future__ import annotations

import hashlib
import os
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


SOURCES_DIR = ROOT / "corpus" / "sources"
DOCUMENTS_DIR = ROOT / "corpus" / "documents"
MANIFEST_PATH = ROOT / "corpus" / "manifest.json"

DOCUMENTS = [
    {
        "id": "regulamento-do-estudante",
        "source": "regulamento-do-estudante.md",
        "pdf": "regulamento-do-estudante.pdf",
        "category": "regulamento",
    },
    {
        "id": "politica-de-cancelamento-e-reembolso",
        "source": "politica-de-cancelamento-e-reembolso.md",
        "pdf": "politica-de-cancelamento-e-reembolso.pdf",
        "category": "cancelamento",
    },
    {
        "id": "guia-de-certificados",
        "source": "guia-de-certificados.md",
        "pdf": "guia-de-certificados.pdf",
        "category": "certificados",
    },
    {
        "id": "faq-de-cursos-e-matriculas",
        "source": "faq-de-cursos-e-matriculas.md",
        "pdf": "faq-de-cursos-e-matriculas.pdf",
        "category": "faq",
    },
    {
        "id": "politica-de-privacidade",
        "source": "politica-de-privacidade.md",
        "pdf": "politica-de-privacidade.pdf",
        "category": "privacidade",
    },
]


@dataclass(frozen=True)
class Metadata:
    title: str
    identifier: str
    version: str
    effective_date: str


class EduDocsCanvas(canvas.Canvas):
    """Canvas com metadados fixos e rodapé padronizado."""

    def __init__(self, *args, title: str, version: str, effective_date: str, **kwargs):
        kwargs["pageCompression"] = 0
        kwargs["invariant"] = 1
        super().__init__(*args, **kwargs)
        self._title = title
        self._version = version
        self._effective_date = effective_date
        self.setAuthor("EduDocs Academy")
        self.setCreator("EduDocs AI corpus generator")
        self.setProducer("EduDocs AI")
        self.setSubject("Corpus educacional fictício")
        self.setTitle(title)

    def save(self) -> None:
        info = self._doc.info
        fixed_date = "D:20260701000000+00'00'"
        info.creationDate = fixed_date
        info.modDate = fixed_date
        super().save()


def find_unicode_font() -> Path:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]

    for path in candidates:
        if path.is_file():
            return path

    raise FileNotFoundError(
        "Fonte Unicode compatível não encontrada. Instale DejaVu Sans no sistema sem versionar arquivos de fonte."
    )


def parse_metadata(markdown: str) -> Metadata:
    title_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    identifier_match = re.search(r"^\*\*Identificador:\*\*\s+(.+)$", markdown, flags=re.MULTILINE)
    version_match = re.search(r"^\*\*Versão:\*\*\s+(.+)$", markdown, flags=re.MULTILINE)
    date_match = re.search(r"^\*\*Data de vigência:\*\*\s+(.+)$", markdown, flags=re.MULTILINE)

    if not all([title_match, identifier_match, version_match, date_match]):
        raise ValueError("Markdown sem título, identificador, versão ou data de vigência.")

    return Metadata(
        title=title_match.group(1).strip(),
        identifier=identifier_match.group(1).strip(),
        version=version_match.group(1).strip(),
        effective_date=date_match.group(1).strip(),
    )


def paragraph_text(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r"<font name='DejaVuSansMono'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "EduDocsTitle",
            parent=base["Title"],
            fontName="DejaVuSans-Bold",
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            spaceAfter=20,
        ),
        "subtitle": ParagraphStyle(
            "EduDocsSubtitle",
            parent=base["Normal"],
            fontName="DejaVuSans",
            fontSize=10,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "EduDocsH1",
            parent=base["Heading1"],
            fontName="DejaVuSans-Bold",
            fontSize=16,
            leading=21,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "EduDocsH2",
            parent=base["Heading2"],
            fontName="DejaVuSans-Bold",
            fontSize=13,
            leading=18,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "EduDocsBody",
            parent=base["BodyText"],
            fontName="DejaVuSans",
            fontSize=10.5,
            leading=15,
            alignment=TA_LEFT,
            spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "EduDocsBullet",
            parent=base["BodyText"],
            fontName="DejaVuSans",
            fontSize=10.5,
            leading=15,
            leftIndent=14,
            firstLineIndent=-8,
            spaceAfter=5,
        ),
    }


def markdown_to_story(markdown: str, metadata: Metadata) -> list:
    styles = build_styles()
    story: list = [
        Paragraph("EduDocs Academy", styles["subtitle"]),
        Paragraph(metadata.title, styles["title"]),
        Paragraph(f"Identificador: {metadata.identifier}", styles["subtitle"]),
        Paragraph(f"Versão: {metadata.version}", styles["subtitle"]),
        Paragraph(f"Data de vigência: {metadata.effective_date}", styles["subtitle"]),
        Spacer(1, 0.5 * cm),
        Paragraph(
            "Documento fictício para validação técnica do EduDocs AI. Não representa política real.",
            styles["subtitle"],
        ),
        PageBreak(),
    ]

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 0.1 * cm))
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            story.append(Paragraph(paragraph_text(line[3:]), styles["h1"]))
            continue
        if line.startswith("### "):
            story.append(Paragraph(paragraph_text(line[4:]), styles["h2"]))
            continue
        if line.startswith("- "):
            story.append(Paragraph("• " + paragraph_text(line[2:]), styles["bullet"]))
            continue
        if re.match(r"^\d+\.\s+", line):
            story.append(Paragraph(paragraph_text(line), styles["bullet"]))
            continue
        story.append(Paragraph(paragraph_text(line), styles["body"]))

    return story


def add_header_footer(pdf_canvas: canvas.Canvas, doc: SimpleDocTemplate, metadata: Metadata) -> None:
    width, height = A4
    page = pdf_canvas.getPageNumber()
    pdf_canvas.saveState()
    pdf_canvas.setFont("DejaVuSans", 8)
    pdf_canvas.setFillColor(colors.HexColor("#475569"))
    pdf_canvas.drawString(1.8 * cm, height - 1.1 * cm, "EduDocs Academy")
    pdf_canvas.drawRightString(width - 1.8 * cm, height - 1.1 * cm, f"{metadata.title} · v{metadata.version}")
    pdf_canvas.line(1.8 * cm, height - 1.25 * cm, width - 1.8 * cm, height - 1.25 * cm)
    pdf_canvas.drawString(1.8 * cm, 1.25 * cm, "Conteúdo fictício para testes")
    pdf_canvas.drawRightString(width - 1.8 * cm, 1.25 * cm, f"Página {page}")
    pdf_canvas.restoreState()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_pdf(source_path: Path, pdf_path: Path) -> Metadata:
    markdown = source_path.read_text(encoding="utf-8")
    metadata = parse_metadata(markdown)
    story = markdown_to_story(markdown, metadata)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(dir=pdf_path.parent, suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        doc = SimpleDocTemplate(
            str(tmp_path),
            pagesize=A4,
            rightMargin=1.8 * cm,
            leftMargin=1.8 * cm,
            topMargin=1.7 * cm,
            bottomMargin=1.8 * cm,
            title=metadata.title,
            author="EduDocs Academy",
            creator="EduDocs AI corpus generator",
        )
        doc.build(
            story,
            onFirstPage=lambda c, d: add_header_footer(c, d, metadata),
            onLaterPages=lambda c, d: add_header_footer(c, d, metadata),
            canvasmaker=lambda *args, **kwargs: EduDocsCanvas(
                *args,
                title=metadata.title,
                version=metadata.version,
                effective_date=metadata.effective_date,
                **kwargs,
            ),
        )
        tmp_path.replace(pdf_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return metadata


def main() -> int:
    font_path = find_unicode_font()
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(font_path)))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(font_path.parent / "DejaVuSans-Bold.ttf")))
    mono_path = font_path.parent / "DejaVuSansMono.ttf"
    if not mono_path.is_file():
        raise FileNotFoundError("Fonte DejaVu Sans Mono não encontrada para renderização de trechos monoespaçados.")
    pdfmetrics.registerFont(TTFont("DejaVuSansMono", str(mono_path)))

    manifest_documents = []
    for document in DOCUMENTS:
        source_path = SOURCES_DIR / document["source"]
        pdf_path = DOCUMENTS_DIR / document["pdf"]
        if not source_path.is_file():
            raise FileNotFoundError(f"Fonte Markdown ausente: {source_path.relative_to(ROOT)}")

        metadata = generate_pdf(source_path, pdf_path)
        if metadata.identifier != document["id"]:
            raise ValueError(f"Identificador divergente em {source_path.relative_to(ROOT)}")

        manifest_documents.append(
            {
                "id": metadata.identifier,
                "title": metadata.title,
                "version": metadata.version,
                "effective_date": metadata.effective_date,
                "source_path": str(source_path.relative_to(ROOT)),
                "pdf_path": str(pdf_path.relative_to(ROOT)),
                "category": document["category"],
                "language": "pt-BR",
                "sha256": sha256(pdf_path),
                "enabled": True,
            }
        )

    manifest = {
        "name": "EduDocs Academy Corpus",
        "version": "1.0",
        "generated_by": "scripts/generate_corpus_pdfs.py",
        "documents": manifest_documents,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {len(manifest_documents)} PDFs gerados e manifesto atualizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
