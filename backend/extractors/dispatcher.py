"""Dispatch helpers for choosing the right extractor based on file type."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from .docx_extractor import extract_text_from_docx
from .ocr_extractor import ocr_image_or_pdf
from .pdf_extractor import extract_text_from_pdf
from .txt_extractor import extract_text_from_txt


def extract_text_from_file(path: str, filename: Optional[str] = None, content_type: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
    """Return extracted text and metadata about the extraction."""

    detected = detect_file_type(path, filename, content_type)
    text = ""
    metadata: Dict[str, str] = {"detected_type": detected}

    if detected == "txt":
        text = extract_text_from_txt(path)
    elif detected == "docx":
        text = extract_text_from_docx(path)
    elif detected == "pdf":
        text = extract_text_from_pdf(path)
    else:
        # Fallback: best-effort text read
        text = extract_text_from_txt(path)
        metadata["fallback"] = "txt"

    if not text.strip():
        if detected == "pdf" or _looks_like_image(filename, path):
            ocr_text = ocr_image_or_pdf(path)
            if ocr_text.strip():
                text = ocr_text
                metadata["ocr_used"] = True

    return text, metadata


def detect_file_type(path: str, filename: Optional[str] = None, content_type: Optional[str] = None) -> str:
    ext = ""

    if filename:
        ext = Path(filename).suffix.lower()
    if not ext:
        ext = Path(path).suffix.lower()

    if content_type:
        if "pdf" in content_type:
            return "pdf"
        if "word" in content_type or "officedocument" in content_type:
            return "docx"
        if "text" in content_type or "plain" in content_type:
            return "txt"

    if ext in {".txt", ".md", ".text", ".json"}:
        return "txt"
    if ext in {".docx"}:
        return "docx"
    if ext in {".pdf"}:
        return "pdf"

    return "txt"


def _looks_like_image(filename: Optional[str], path: str) -> bool:
    candidates = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    for target in (filename, path):
        if not target:
            continue
        if Path(str(target)).suffix.lower() in candidates:
            return True
    return False
