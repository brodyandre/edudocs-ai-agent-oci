from __future__ import annotations

import re

from app.documents.pdf import PageText

HEADER_FOOTER_PATTERNS = [
    re.compile(r"^EduDocs Academy$"),
    re.compile(r"^Conteúdo fictício para testes$"),
    re.compile(r"^Página\s+\d+$"),
    re.compile(r"^.+\s+·\s+v\d+(?:\.\d+)*$"),
]


def normalize_text(text: str) -> str:
    """Normaliza texto preservando parágrafos, listas, números e títulos."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines: list[str] = []
    previous_blank = False

    for raw_line in text.split("\n"):
        line = re.sub(r"[\t\f\v ]+", " ", raw_line).strip()
        if any(pattern.match(line) for pattern in HEADER_FOOTER_PATTERNS):
            continue
        if not line:
            if normalized_lines and not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue
        normalized_lines.append(line)
        previous_blank = False

    return "\n".join(normalized_lines).strip()


def normalize_pages(pages: list[PageText]) -> list[PageText]:
    return [
        PageText(
            document_id=page.document_id,
            document_title=page.document_title,
            document_version=page.document_version,
            page_number=page.page_number,
            text=normalize_text(page.text),
        )
        for page in pages
    ]
