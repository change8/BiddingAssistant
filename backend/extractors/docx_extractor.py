from __future__ import annotations

from typing import List
from xml.etree import ElementTree
from zipfile import ZipFile

try:
    import docx  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    docx = None


def extract_text_from_docx(path: str) -> str:
    """Extract text from a .docx file using python-docx when available."""

    if docx is not None:
        try:
            document = docx.Document(path)
            parts: List[str] = []
            parts.extend(p.text.strip() for p in document.paragraphs if p.text and p.text.strip())
            for table in getattr(document, "tables", []):
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
                    if cells:
                        parts.append("\t".join(cells))
            return "\n".join(parts)
        except Exception:
            pass

    # Fallback: parse XML
    try:
        with ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")
    except Exception:
        return ""

    try:
        tree = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return ""

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    texts: List[str] = []
    for paragraph in tree.iter(f"{namespace}p"):
        buffer = [node.text for node in paragraph.iter(f"{namespace}t") if node.text]
        if buffer:
            texts.append("".join(buffer).strip())
    return "\n".join(texts)
