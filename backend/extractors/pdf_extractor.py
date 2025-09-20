from __future__ import annotations

from typing import List

try:
    from pdfminer.high_level import extract_text  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    extract_text = None  # type: ignore


def extract_text_from_pdf(path: str) -> str:
    """Best-effort PDF text extraction."""

    if extract_text is not None:
        try:
            return extract_text(path)
        except Exception:
            pass

    try:
        import PyPDF2  # type: ignore

        text_parts: List[str] = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
    except Exception:
        return ""
