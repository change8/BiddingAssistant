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
        llm_result = self.llm.analyze_adaptive(cleaned)

        return {
            "summary": llm_result.get("summary", ""),
            "critical_requirements": llm_result.get("critical_requirements", []),
            "cost_factors": llm_result.get("cost_factors", []),
            "timeline": llm_result.get("timeline", []),
            "risks": llm_result.get("risks", []),
            "unusual_findings": llm_result.get("unusual_findings", []),
            "clarification_needed": llm_result.get("clarification_needed", []),
            "metadata": {"preprocess": preprocess_meta, "raw_response": llm_result.get("raw_response")},
        }
