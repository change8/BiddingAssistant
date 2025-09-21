"""Pluggable LLM client abstraction."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

from .retrieval import HeuristicRetriever, TextSegment, split_text_into_segments


class LLMClient:
    """Wrapper around different LLM providers for semantic tasks."""

    def __init__(
        self,
        provider: str = "stub",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.options = kwargs
        self._heuristic = HeuristicRetriever()

    # ------------------------------------------------------------------ public
    def semantic_locate(
        self,
        text: str,
        hints: Iterable[str],
        rule: Dict[str, Any],
        segments: Optional[Iterable[Any]] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        provider = (self.provider or "stub").lower()
        if provider in {"stub", "mock"}:
            return self._heuristic_semantic(text, hints, segments)
        if provider in {"openai", "openai_compatible"}:
            return self._call_openai(text, hints, rule, segments)
        if provider in {"azure_openai", "azure"}:
            return self._call_azure(text, hints, rule, segments)
        # Extend with more providers when needed
        raise NotImplementedError(f"LLM provider '{self.provider}' not implemented")

    def summarize_rule(self, rule: Dict[str, Any], evidences: List[Dict[str, Any]]) -> Dict[str, Any]:
        provider = (self.provider or "stub").lower()
        if provider in {"stub", "mock"}:
            items = []
            for ev in evidences:
                text = (ev.get("snippet") or ev.get("evidence") or "").strip()
                if not text:
                    continue
                items.append({"requirement": text, "evidence": text})
                if len(items) >= 5:
                    break
            return {"summary": rule.get("description"), "items": items}
        if provider in {"openai", "openai_compatible"}:
            return self._call_openai_summary(rule, evidences)
        if provider in {"azure_openai", "azure"}:
            return self._call_azure_summary(rule, evidences)
        raise NotImplementedError(f"LLM provider '{self.provider}' not implemented")

    # ----------------------------------------------------------------- helpers
    def _heuristic_semantic(
        self,
        text: str,
        hints: Iterable[str],
        segments: Optional[Iterable[Any]] = None,
    ) -> List[Dict[str, Any]]:
        if segments is None:
            segments = self._heuristic.locate_candidates(text, hints)
        results: List[Dict[str, Any]] = []
        for seg in segments:
            if isinstance(seg, TextSegment):
                start = seg.start
                length = seg.length
                evidence = seg.text
                score = seg.score
            else:
                start = getattr(seg, "start", 0)
                length = getattr(seg, "length", 0)
                evidence = getattr(seg, "text", "") or getattr(seg, "evidence", "")
                score = getattr(seg, "score", 0.0)
                if not evidence and length:
                    evidence = text[start : start + length]
            if not evidence:
                continue
            if not score:
                hints_lower = [h.lower() for h in hints if h]
                score = max(
                    (SequenceMatcher(a=evidence.lower(), b=h).ratio() for h in hints_lower),
                    default=0.0,
                )
            results.append(
                {
                    "start": start,
                    "length": length or len(evidence),
                    "evidence": evidence,
                    "score": float(score),
                }
            )
        return results

    # ---------------------------------------------------------------- requests
    def _call_openai(
        self,
        text: str,
        hints: Iterable[str],
        rule: Dict[str, Any],
        segments: Optional[Iterable[Any]] = None,
    ) -> List[Dict[str, Any]]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key")
        if not api_key:
            raise RuntimeError("缺少 OpenAI API key")
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        model = self.model or self.options.get("model") or "gpt-4o-mini"
        prompt = self._build_semantic_prompt(text, hints, rule, segments)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是投标文件分析助手，输出 JSON"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_semantic_response(content)

    def _call_openai_summary(
        self,
        rule: Dict[str, Any],
        evidences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key")
        if not api_key:
            raise RuntimeError("缺少 OpenAI API key")
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        model = self.model or self.options.get("model") or "gpt-4o-mini"
        prompt = self._build_summary_prompt(rule, evidences)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是投标标书分析助手，必须返回 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_summary_response(content)

    def _call_azure(
        self,
        text: str,
        hints: Iterable[str],
        rule: Dict[str, Any],
        segments: Optional[Iterable[Any]] = None,
    ) -> List[Dict[str, Any]]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 Azure OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key") or self.options.get("key")
        endpoint = self.base_url or self.options.get("endpoint")
        deployment = self.options.get("deployment") or self.model
        if not (api_key and endpoint and deployment):
            raise RuntimeError("Azure OpenAI 配置缺失 (api_key / endpoint / deployment)")
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version=2023-07-01-preview"
        prompt = self._build_semantic_prompt(text, hints, rule, segments)
        payload = {
            "messages": [
                {"role": "system", "content": "你是投标文件分析助手，输出 JSON"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_semantic_response(content)

    def _call_azure_summary(
        self,
        rule: Dict[str, Any],
        evidences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 Azure OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key") or self.options.get("key")
        endpoint = self.base_url or self.options.get("endpoint")
        deployment = self.options.get("deployment") or self.model
        if not (api_key and endpoint and deployment):
            raise RuntimeError("Azure OpenAI 配置缺失 (api_key / endpoint / deployment)")
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version=2023-07-01-preview"
        prompt = self._build_summary_prompt(rule, evidences)
        payload = {
            "messages": [
                {"role": "system", "content": "你是投标标书分析助手，必须返回 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_summary_response(content)

    # ---------------------------------------------------------------- parsing
    def _build_semantic_prompt(
        self,
        text: str,
        hints: Iterable[str],
        rule: Dict[str, Any],
        segments: Optional[Iterable[Any]] = None,
    ) -> str:
        hints_list = list(hints)
        preview_segments = []
        if segments:
            for seg in segments:
                snippet = getattr(seg, "text", None) or getattr(seg, "evidence", None)
                if snippet:
                    preview_segments.append(snippet[:400])
        if not preview_segments:
            # Provide fallback segments to reduce prompt size
            fallback = split_text_into_segments(text, max_chars=400)
            preview_segments = [seg.text for seg in fallback[:5]]

        prompt = {
            "task": "semantic_locate",
            "rule": {"id": rule.get("id"), "description": rule.get("description"), "category": rule.get("category")},
            "hints": hints_list,
            "segments": preview_segments,
            "instruction": "找出与 hints 强相关的段落，返回 JSON 列表，每项包含 start, length, evidence。start/length 基于整份文本的字符索引。若无匹配返回空数组。",
        }
        return json.dumps(prompt, ensure_ascii=False)

    def _build_summary_prompt(self, rule: Dict[str, Any], evidences: List[Dict[str, Any]]) -> str:
        trimmed = []
        for idx, ev in enumerate(evidences, start=1):
            text = (ev.get("snippet") or ev.get("evidence") or "").strip()
            if not text:
                continue
            trimmed.append({"id": idx, "text": text[:1200]})
            if len(trimmed) >= 6:
                break

        payload = {
            "task": "extract_rule_requirements",
            "rule": rule,
            "evidences": trimmed,
            "instruction": "你是一名投标文件分析专家。请仅依据 evidences 内容，提取与 rule 描述相关的明确条款或要求。返回 JSON：{\"summary\": string, \"items\": [{\"requirement\": string, \"evidence\": string}] }。summary 为总体概述；items 中每一项的 requirement 需引用或紧贴原文，evidence 必须摘自提供的 evidences 文本，若无足够信息则返回空数组。禁止臆造。",
        }
        return json.dumps(payload, ensure_ascii=False)

    def _parse_semantic_response(self, content: str) -> List[Dict[str, Any]]:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "candidates" in parsed:
                candidates = parsed["candidates"]
            else:
                candidates = parsed
            if not isinstance(candidates, list):
                return []
            results: List[Dict[str, Any]] = []
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                start = int(item.get("start", 0))
                length = int(item.get("length", 0))
                evidence = item.get("evidence") or ""
                results.append({"start": start, "length": length, "evidence": evidence})
            return results
        except Exception:
            return []

    def _parse_summary_response(self, content: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return {}
            summary = parsed.get("summary") or parsed.get("main") or parsed.get("overview")
            items = parsed.get("items") or parsed.get("bullet_points") or []
            normalized = []
            if isinstance(items, dict):
                items = [items]
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        requirement = str(item.get("requirement") or item.get("text") or item.get("point") or "").strip()
                        evidence = str(item.get("evidence") or item.get("quote") or item.get("source") or "").strip()
                        if requirement:
                            normalized.append({"requirement": requirement, "evidence": evidence})
                    else:
                        text = str(item).strip()
                        if text:
                            normalized.append({"requirement": text, "evidence": text})
            elif isinstance(items, str) and items.strip():
                normalized.append({"requirement": items.strip(), "evidence": items.strip()})
            return {"summary": summary, "items": normalized}
        except Exception:
            return {}
