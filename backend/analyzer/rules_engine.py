from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Rule:
    id: str
    category: str
    description: str
    match_type: str  # keyword | regex | semantic
    patterns: List[str]
    severity: str = "medium"  # low | medium | high | critical
    advice: Optional[str] = None


@dataclass
class Hit:
    rule_id: str
    category: str
    severity: str
    snippet: str
    evidence: str
    advice: Optional[str]


class RulesEngine:
    def __init__(self, rules: List[Rule], llm: Optional[Any] = None, retriever: Optional[Any] = None):
        self.rules = rules
        self.llm = llm
        self.retriever = retriever

    def analyze(self, text: str) -> Dict[str, Any]:
        hits: List[Hit] = []
        for r in self.rules:
            if r.match_type == "keyword":
                hits.extend(self._match_keyword(r, text))
            elif r.match_type == "regex":
                hits.extend(self._match_regex(r, text))
            elif r.match_type == "semantic":
                hits.extend(self._match_semantic(r, text))

        # group by category
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for h in hits:
            categories.setdefault(h.category, []).append(
                {
                    "rule_id": h.rule_id,
                    "severity": h.severity,
                    "snippet": h.snippet,
                    "evidence": h.evidence,
                    "advice": h.advice,
                }
            )

        # sort items in each category by severity weight
        weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        for cat in categories:
            categories[cat].sort(key=lambda x: -weight.get(x.get("severity", "medium"), 2))

        return {
            "summary": self._build_summary(categories),
            "categories": categories,
        }

    def _build_summary(self, categories: Dict[str, Any]) -> Dict[str, Any]:
        return {cat: len(items) for cat, items in categories.items()}

    def _match_keyword(self, rule: Rule, text: str) -> List[Hit]:
        hits: List[Hit] = []
        for kw in rule.patterns:
            # simple case-insensitive search (Chinese unaffected)
            idx = text.lower().find(kw.lower())
            if idx >= 0:
                snippet = self._context(text, idx, len(kw))
                hits.append(
                    Hit(
                        rule_id=rule.id,
                        category=rule.category,
                        severity=rule.severity,
                        snippet=snippet,
                        evidence=kw,
                        advice=rule.advice,
                    )
                )
        return hits

    def _match_regex(self, rule: Rule, text: str) -> List[Hit]:
        hits: List[Hit] = []
        for pat in rule.patterns:
            try:
                for m in re.finditer(pat, text, flags=re.IGNORECASE | re.MULTILINE):
                    snippet = self._context(text, m.start(), m.end() - m.start())
                    hits.append(
                        Hit(
                            rule_id=rule.id,
                            category=rule.category,
                            severity=rule.severity,
                            snippet=snippet,
                            evidence=m.group(0),
                            advice=rule.advice,
                        )
                    )
            except re.error:
                # ignore invalid regex in template
                continue
        return hits

    def _match_semantic(self, rule: Rule, text: str) -> List[Hit]:
        hits: List[Hit] = []
        segments = None
        if self.retriever:
            try:
                segments = self.retriever.locate_candidates(text, hints=rule.patterns)
            except Exception:
                segments = None
        if not self.llm and segments:
            candidates = [
                {"start": seg.start, "length": seg.length, "evidence": seg.text, "score": getattr(seg, "score", 0.0)}
                for seg in segments
            ]
        elif not self.llm:
            return hits
        else:
            candidates = self.llm.semantic_locate(text=text, hints=rule.patterns, rule=rule.__dict__, segments=segments)
        try:
            for c in candidates or []:
                idx = max(0, c.get("start", 0))
                length = max(0, c.get("length", 0))
                snippet = self._context(text, idx, length)
                evidence = c.get("evidence", snippet)
                hits.append(
                    Hit(
                        rule_id=rule.id,
                        category=rule.category,
                        severity=rule.severity,
                        snippet=snippet,
                        evidence=evidence,
                        advice=rule.advice,
                    )
                )
        except Exception:
            pass
        return hits

    @staticmethod
    def _context(text: str, start: int, length: int, window: int = 90) -> str:
        s = max(0, start - window)
        e = min(len(text), start + length + window)
        return text[s:e].strip()
