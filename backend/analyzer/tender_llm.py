from __future__ import annotations

from typing import Any, Dict, List

from .framework import DEFAULT_FRAMEWORK, FrameworkCategory
from .llm import LLMClient
from .preprocess import preprocess_text


SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class TenderLLMAnalyzer:
    """High-level LLM-only analyzer that relies on the model to understand the tender."""

    def __init__(
        self,
        llm: LLMClient,
        categories: List[FrameworkCategory] | None = None,
    ) -> None:
        self.llm = llm
        self.categories = categories or DEFAULT_FRAMEWORK
        self.category_index = {cat.id: cat for cat in self.categories}

    def analyze(self, text: str) -> Dict[str, Any]:
        cleaned, preprocess_meta = preprocess_text(text)
        llm_result = self.llm.analyze_framework(cleaned, self.categories)
        categories = llm_result.get("categories", [])
        timeline = llm_result.get("timeline", {"milestones": [], "remark": ""})

        if not categories or all(not cat.get("items") for cat in categories if isinstance(cat, dict)):
            fallback = self.llm.analyze_framework(cleaned, self.categories)
            categories = fallback.get("categories", categories)
            timeline = fallback.get("timeline", timeline)
            llm_result.setdefault("raw_response", fallback.get("raw_response"))

        formatted: Dict[str, List[Dict[str, Any]]] = {}
        summary: Dict[str, int] = {}

        for cat in categories:
            cat_id = cat.get("id") or "unknown"
            meta = self.category_index.get(cat_id)
            title = cat.get("title") or (meta.title if meta else cat_id)
            items = []
            for item in cat.get("items", []):
                if not isinstance(item, dict):
                    continue
                severity = (item.get("severity") or (meta.severity if meta else "medium")).lower()
                if severity not in SEVERITY_WEIGHT:
                    severity = meta.severity if meta else "medium"
                items.append(
                    {
                        "title": item.get("title") or item.get("name") or title,
                        "summary": item.get("description") or item.get("detail") or "",
                        "evidence": item.get("evidence") or "",
                        "recommendation": item.get("recommendation") or "",
                        "severity": severity,
                    }
                )
            if not items:
                continue
            formatted.setdefault(title, []).extend(items)
            summary[title] = len(items)

        # sort items in each category by severity weight
        for title, items in formatted.items():
            items.sort(key=lambda x: -SEVERITY_WEIGHT.get(x.get("severity", "medium"), 2))

        return {
            "summary": summary,
            "categories": formatted,
            "timeline": timeline,
            "metadata": {"preprocess": preprocess_meta, "raw_response": llm_result.get("raw_response")},
        }
