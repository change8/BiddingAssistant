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
    description: str
    start: int
    length: int
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

        aggregated = self._aggregate_hits(hits)

        summary = {cat: len(items) for cat, items in aggregated.items()}

        return {
            "summary": summary,
            "categories": aggregated,
        }

    def _match_keyword(self, rule: Rule, text: str) -> List[Hit]:
        hits: List[Hit] = []
        lower_text = text.lower()
        for kw in rule.patterns:
            pattern = kw.lower()
            idx = lower_text.find(pattern)
            while idx >= 0:
                snippet = self._context(text, idx, len(kw))
                hits.append(
                    Hit(
                        rule_id=rule.id,
                        category=rule.category,
                        severity=rule.severity,
                        snippet=snippet,
                        evidence=text[idx : idx + len(kw)],
                        description=rule.description,
                        start=idx,
                        length=len(kw),
                        advice=rule.advice,
                    )
                )
                idx = lower_text.find(pattern, idx + len(pattern) if len(pattern) else idx + 1)
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
                            description=rule.description,
                            start=m.start(),
                            length=m.end() - m.start(),
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
                        description=rule.description,
                        start=idx,
                        length=length,
                        advice=rule.advice,
                    )
                )
        except Exception:
            pass
        return hits

    @staticmethod
    def _context(text: str, start: int, length: int, window: int = 120) -> str:
        if not text:
            return ""

        s = max(0, start - window)
        e = min(len(text), start + length + window)

        # try to expand to sentence boundaries using common punctuation
        punct = "。．！？!?；;\n"
        left = start
        while left > 0 and text[left - 1] not in punct:
            left -= 1
            if left <= s:
                break

        right = start + length
        while right < len(text) and text[right] not in punct:
            right += 1
            if right >= e:
                break

        snippet = text[max(left, s):min(right + 1, e)].strip()
        if not snippet:
            snippet = text[s:e].strip()
        return snippet

    def _aggregate_hits(self, hits: List[Hit]) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for hit in hits:
            key = f"{hit.category}::{hit.rule_id}"
            bucket = grouped.get(key)
            evidence_payload = {
                "snippet": hit.snippet,
                "evidence": hit.evidence,
                "start": hit.start,
                "length": hit.length,
            }
            if not bucket:
                bucket = {
                    "rule_id": hit.rule_id,
                    "description": hit.description,
                    "severity": hit.severity,
                    "advice": hit.advice,
                    "category": hit.category,
                    "evidences": [evidence_payload],
                }
                grouped[key] = bucket
            else:
                bucket["evidences"].append(evidence_payload)

        categories: Dict[str, List[Dict[str, Any]]] = {}
        weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        for bucket in grouped.values():
            summary = self._summarize_bucket(bucket)
            entry = {
                "rule_id": bucket["rule_id"],
                "description": bucket["description"],
                "severity": bucket["severity"],
                "summary": summary.get("summary"),
                "items": summary.get("items", []),
                "evidences": bucket["evidences"],
                "advice": bucket.get("advice"),
            }
            categories.setdefault(bucket["category"], []).append(entry)

        for cat in categories:
            categories[cat].sort(key=lambda x: -weight.get(x.get("severity", "medium"), 2))

        return categories

    def _summarize_bucket(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        evidences = bucket.get("evidences", [])
        if not evidences:
            return {"summary": bucket.get("description"), "items": []}
        if not self.llm:
            items = [ev.get("snippet") or ev.get("evidence") for ev in evidences if ev.get("snippet") or ev.get("evidence")]
            return {"summary": bucket.get("description"), "items": items[:5]}
        try:
            return self.llm.summarize_rule(
                rule={
                    "id": bucket["rule_id"],
                    "description": bucket["description"],
                    "severity": bucket["severity"],
                    "category": bucket["category"],
                },
                evidences=evidences,
            ) or {"summary": bucket.get("description"), "items": []}
        except Exception:
            items = [ev.get("snippet") or ev.get("evidence") for ev in evidences if ev.get("snippet") or ev.get("evidence")]
            return {"summary": bucket.get("description"), "items": items[:5]}
