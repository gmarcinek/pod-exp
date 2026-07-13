from __future__ import annotations

import html
import json
import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

from config import DEBATES_DIR
from editorial_store import assemble_editorial_document


def _load_editorial_record(editorial_id: str) -> dict:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", editorial_id)
    path = DEBATES_DIR / f"{safe_id}.json"
    if not path.exists():
        raise FileNotFoundError("Nie znaleziono sesji redakcyjnej.")
    record = json.loads(path.read_text(encoding="utf-8"))
    if str(record.get("type") or "") != "edit":
        raise ValueError("Wskazany rekord nie jest sesją redakcyjną.")
    return record


def _editorial_html(record: dict) -> str:
    title = html.escape(str(record.get("topic") or "Sesja redakcyjna"))
    text = _editorial_text(record)
    paragraphs = [
        f"<p>{html.escape(paragraph).replace(chr(10), '<br>')}</p>"
        for paragraph in text.split("\n\n")
    ]
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ max-width: 48rem; margin: 3rem auto; padding: 0 1.5rem; color: #1a1a1a; font: 12pt/1.65 Georgia, serif; }}
h1 {{ font-size: 24pt; line-height: 1.2; }}
p {{ margin: 0 0 1.1em; }}
</style>
</head>
<body>
<h1>{title}</h1>
{''.join(paragraphs)}
</body>
</html>"""


def _editorial_docx(record: dict) -> bytes:
    title = str(record.get("topic") or "Sesja redakcyjna")
    text = _editorial_text(record)
    paragraphs = [title, *text.split("\n")]
    body = "".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(paragraph)}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    relationships = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def _editorial_text(record: dict) -> str:
    editorial_id = str(record.get("id") or "")
    stored_text = assemble_editorial_document(editorial_id=editorial_id)
    if stored_text is not None:
        return stored_text
    return str(record.get("final_text") or "")


def build_editorial_export(editorial_id: str, export_format: str) -> tuple[bytes, str, str]:
    record = _load_editorial_record(editorial_id)
    safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(record.get("topic") or "editorial")).strip("-")
    if export_format == "html":
        return _editorial_html(record).encode("utf-8"), "text/html; charset=utf-8", f"{safe_title}.html"
    if export_format == "docx":
        return (
            _editorial_docx(record),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            f"{safe_title}.docx",
        )
    raise ValueError("Obsługiwane formaty eksportu: html, docx.")