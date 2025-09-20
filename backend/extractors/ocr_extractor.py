from __future__ import annotations

from pathlib import Path
from typing import List

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Image = None  # type: ignore

try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore

try:
    from pdf2image import convert_from_path  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    convert_from_path = None  # type: ignore


def ocr_image_or_pdf(path: str) -> str:
    """OCR fallback using pytesseract when available."""

    if pytesseract is None or Image is None:
        return ""

    suffix = Path(path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}:
        with Image.open(path) as img:
            return _ocr_image(img)

    if suffix == ".pdf" and convert_from_path is not None:
        try:
            images = convert_from_path(path)
        except Exception:
            return ""
        texts: List[str] = []
        for img in images:
            texts.append(_ocr_image(img))
        return "\n".join(filter(None, texts))

    return ""


def _ocr_image(image) -> str:
    if pytesseract is None:
        return ""
    try:
        if hasattr(image, "mode") and image.mode not in {"L", "RGB"}:
            image = image.convert("RGB")
        return pytesseract.image_to_string(image, lang="chi_sim+eng")
    except Exception:
        try:
            return pytesseract.image_to_string(image, lang="eng")
        except Exception:
            return ""
