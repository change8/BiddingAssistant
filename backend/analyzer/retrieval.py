"""Retrieval helpers for semantic rule matching."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    np = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore

_PARAGRAPH_RE = re.compile(r".+?(?:\n\s*\n|$)", re.S)


@dataclass
class TextSegment:
    text: str
    start: int
    length: int
    score: float = 0.0


def split_text_into_segments(text: str, max_chars: int = 600) -> List[TextSegment]:
    segments: List[TextSegment] = []
    for match in _PARAGRAPH_RE.finditer(text):
        chunk = match.group(0).strip()
        if not chunk:
            continue
        start = match.start()
        remaining = chunk
        cursor = start
        while len(remaining) > max_chars:
            piece = remaining[:max_chars]
            segments.append(TextSegment(text=piece, start=cursor, length=len(piece)))
            remaining = remaining[max_chars:]
            cursor += len(piece)
        if remaining:
            segments.append(TextSegment(text=remaining, start=cursor, length=len(remaining)))
    return segments


class HeuristicRetriever:
    """Rule hint based retriever using fuzzy string similarity."""

    def __init__(self, threshold: float = 0.45, limit: int = 6, max_chars: int = 600) -> None:
        self.threshold = threshold
        self.limit = limit
        self.max_chars = max_chars

    def locate_candidates(self, text: str, hints: Iterable[str]) -> List[TextSegment]:
        segments = split_text_into_segments(text, max_chars=self.max_chars)
        results: List[TextSegment] = []
        hints_lower = [h.lower() for h in hints if h]
        if not hints_lower:
            return []
        for seg in segments:
            scores = [SequenceMatcher(a=seg.text.lower(), b=h).ratio() for h in hints_lower]
            score = max(scores) if scores else 0.0
            if score >= self.threshold:
                seg.score = score
                results.append(seg)
        results.sort(key=lambda s: s.score, reverse=True)
        return results[: self.limit]


class EmbeddingRetriever:
    """Embedding-based retriever powered by sentence-transformers when available."""

    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese", limit: int = 6, max_chars: int = 600) -> None:
        self.limit = limit
        self.max_chars = max_chars
        if SentenceTransformer is None or np is None:
            self.model = None
        else:
            try:
                self.model = SentenceTransformer(model_name)
            except Exception:
                self.model = None

    def locate_candidates(self, text: str, hints: Iterable[str]) -> List[TextSegment]:
        if not hints:
            return []
        segments = split_text_into_segments(text, max_chars=self.max_chars)
        if not segments:
            return []
        if self.model is None:
            return []
        try:
            segment_embeddings = self.model.encode([seg.text for seg in segments], convert_to_numpy=True, normalize_embeddings=True)
            hint_embeddings = self.model.encode(list(hints), convert_to_numpy=True, normalize_embeddings=True)
        except Exception:
            return []
        scores = segment_embeddings @ hint_embeddings.T  # cosine similarity (normalized)
        best_scores = scores.max(axis=1)
        ranked = sorted(zip(segments, best_scores), key=lambda item: float(item[1]), reverse=True)
        results: List[TextSegment] = []
        for seg, score in ranked[: self.limit]:
            seg.score = float(score)
            results.append(seg)
        return results


def merge_retrievals(*retrievers: Optional[Any]) -> Any:
    """Compose multiple retrievers into one callable."""

    active = [r for r in retrievers if r is not None]
    if not active:
        return None

    class CompositeRetriever:
        def locate_candidates(self, text: str, hints: Iterable[str]) -> List[TextSegment]:
            results: List[TextSegment] = []
            for ret in active:
                try:
                    results.extend(ret.locate_candidates(text, hints))
                except Exception:
                    continue
            # Deduplicate by start position and prefer higher score
            dedup: Dict[int, TextSegment] = {}
            for seg in results:
                existing = dedup.get(seg.start)
                if existing is None or seg.score > existing.score:
                    dedup[seg.start] = seg
            final = sorted(dedup.values(), key=lambda s: s.score, reverse=True)
            return final

    return CompositeRetriever()

