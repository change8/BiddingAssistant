from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel
except Exception:
    # Lightweight fallback to avoid import errors in environments without pydantic
    class BaseModel:  # type: ignore
        def dict(self, *args, **kwargs):
            return self.__dict__


class AnalyzeRequest(BaseModel):
    text: Optional[str] = None
    filename: Optional[str] = None
    keywords: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    async_mode: bool = False


class RuleItem(BaseModel):
    id: str
    category: str
    description: str
    match_type: str
    patterns: List[str]
    severity: str = "medium"
    advice: Optional[str] = None


class AnalyzeResponse(BaseModel):
    summary: Dict[str, int]
    categories: Dict[str, List[Dict[str, Any]]]
