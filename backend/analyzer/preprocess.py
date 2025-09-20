"""Utilities for normalising tender text before running rules analysis."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Tuple

_WHITESPACE_RE = re.compile(r"[\t\f\v]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def preprocess_text(text: str) -> Tuple[str, Dict[str, Any]]:
    """Return cleaned text and lightweight metadata."""

    original_length = len(text)

    # Normalise unicode: convert full-width to half-width where sensible.
    normalised = unicodedata.normalize("NFKC", text)

    # Standardise newlines and strip control chars.
    normalised = normalised.replace("\r\n", "\n").replace("\r", "\n")
    normalised = _CONTROL_RE.sub("", normalised)

    # Collapse whitespace tabs/formfeeds to single spaces and condense blank lines.
    normalised = _WHITESPACE_RE.sub(" ", normalised)
    normalised = _MULTI_NEWLINE_RE.sub("\n\n", normalised)

    cleaned = normalised.strip()

    metadata = {
        "original_length": original_length,
        "clean_length": len(cleaned),
        "line_count": cleaned.count("\n") + 1 if cleaned else 0,
    }
    return cleaned, metadata

