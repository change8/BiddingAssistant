"""Pluggable LLM client abstraction."""

from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

from .adaptive_prompt import build_adaptive_prompt
from .framework import DEFAULT_FRAMEWORK, FrameworkCategory
from .retrieval import HeuristicRetriever, TextSegment, split_text_into_segments

logger = logging.getLogger(__name__)

ADAPTIVE_TAB_SPECS = [
    ("hard_requirements", "废标项/硬性要求"),
    ("scoring_items", "评分项"),
    ("submission_format", "投标形式"),
    ("technical_requirements", "技术要求"),
    ("cost_items", "成本项"),
    ("bid_timeline", "投标日历"),
]


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
        self._no_proxy = {"http": None, "https": None}

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

    def analyze_framework(self, text: str, categories: List[FrameworkCategory] | None = None) -> Dict[str, Any]:
        selected = categories or DEFAULT_FRAMEWORK
        provider = (self.provider or "stub").lower()
        if provider in {"stub", "mock"}:
            return self._heuristic_framework(text, selected)
        if provider in {"openai", "openai_compatible"}:
            return self._call_openai_framework(text, selected)
        if provider in {"azure_openai", "azure"}:
            return self._call_azure_framework(text, selected)
        raise NotImplementedError(f"LLM provider '{self.provider}' not implemented")

    def analyze_adaptive(self, text: str) -> Dict[str, Any]:
        prompt_payload = build_adaptive_prompt(text)
        provider = (self.provider or "stub").lower()
        if provider in {"stub", "mock"}:
            return self._heuristic_adaptive(text)
        if provider in {"openai", "openai_compatible"}:
            return self._call_openai_adaptive(prompt_payload)
        if provider in {"azure_openai", "azure"}:
            return self._call_azure_adaptive(prompt_payload)
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
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout, proxies=self._no_proxy)
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
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout, proxies=self._no_proxy)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_summary_response(content)

    def _call_openai_adaptive(self, prompt_payload: Dict[str, Any]) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key")
        if not api_key:
            raise RuntimeError("缺少 OpenAI API key")
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        model = self.model or self.options.get("model") or "gpt-4o-mini"
        system_prompt = prompt_payload.get("system")
        messages = prompt_payload.get("messages") or []
        assembled_messages: List[Dict[str, Any]] = []
        if system_prompt:
            assembled_messages.append({"role": "system", "content": system_prompt})
        assembled_messages.extend(messages)
        payload = {
            "model": model,
            "messages": assembled_messages,
            "temperature": 0,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                proxies=self._no_proxy,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = self._parse_adaptive_response(content)
            parsed.setdefault("raw_response", content)
            return parsed
        except (requests.Timeout, requests.ReadTimeout) as exc:
            logger.warning("Adaptive LLM timeout: %s", exc)
            fallback = self._heuristic_adaptive(prompt_payload.get("raw_text", ""))
            fallback.setdefault("raw_response", "timeout")
            return fallback
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.warning("Adaptive LLM HTTPError (%s): %s", exc, body)
            fallback = self._heuristic_adaptive(prompt_payload.get("raw_text", ""))
            fallback.setdefault("raw_response", body)
            return fallback

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
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout, proxies=self._no_proxy)
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
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout, proxies=self._no_proxy)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_summary_response(content)

    def _call_azure_adaptive(self, prompt_payload: Dict[str, Any]) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 Azure OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key") or self.options.get("key")
        endpoint = self.base_url or self.options.get("endpoint")
        deployment = self.options.get("deployment") or self.model
        if not (api_key and endpoint and deployment):
            raise RuntimeError("Azure OpenAI 配置缺失 (api_key / endpoint / deployment)")
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version=2023-07-01-preview"
        system_prompt = prompt_payload.get("system")
        messages = prompt_payload.get("messages") or []
        assembled_messages: List[Dict[str, Any]] = []
        if system_prompt:
            assembled_messages.append({"role": "system", "content": system_prompt})
        assembled_messages.extend(messages)
        payload = {
            "messages": assembled_messages,
            "temperature": 0,
            "stream": False,
        }
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                proxies=self._no_proxy,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = self._parse_adaptive_response(content)
            parsed.setdefault("raw_response", content)
            return parsed
        except (requests.Timeout, requests.ReadTimeout) as exc:
            logger.warning("Azure adaptive timeout: %s", exc)
            fallback = self._heuristic_adaptive(prompt_payload.get("raw_text", ""))
            fallback.setdefault("raw_response", "timeout")
            return fallback
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.warning("Azure adaptive HTTPError (%s): %s", exc, body)
            fallback = self._heuristic_adaptive(prompt_payload.get("raw_text", ""))
            fallback.setdefault("raw_response", body)
            return fallback

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

    def _default_adaptive_tabs(self) -> List[Dict[str, Any]]:
        return [{"id": tab_id, "title": title, "items": []} for tab_id, title in ADAPTIVE_TAB_SPECS]

    def _normalise_adaptive_items(self, value: Any) -> List[Dict[str, Any]]:
        if isinstance(value, list):
            iterable = value
        elif isinstance(value, dict):
            iterable = [value]
        else:
            return []
        items: List[Dict[str, Any]] = []
        for item in iterable:
            if not isinstance(item, dict):
                continue
            normalised: Dict[str, Any] = {}
            for key, val in item.items():
                if key in {"source_start", "source_end"}:
                    try:
                        normalised[key] = int(val)
                    except (ValueError, TypeError):
                        continue
                else:
                    normalised[key] = val
            items.append(normalised)
        return items

    def _normalise_adaptive_tabs(self, tabs: Any) -> List[Dict[str, Any]]:
        defaults: Dict[str, Dict[str, Any]] = {tab_id: {"id": tab_id, "title": title, "items": []} for tab_id, title in ADAPTIVE_TAB_SPECS}
        if isinstance(tabs, dict):
            iterable = tabs.values()
        elif isinstance(tabs, list):
            iterable = tabs
        else:
            iterable = []
        for tab in iterable:
            if not isinstance(tab, dict):
                continue
            tab_id = str(tab.get("id") or tab.get("key") or "").strip()
            if tab_id and tab_id in defaults:
                entry = defaults[tab_id]
                title = tab.get("title")
                if isinstance(title, str) and title.strip():
                    entry["title"] = title.strip()
                entry["items"] = self._normalise_adaptive_items(tab.get("items"))
        return [defaults[tab_id] for tab_id, _ in ADAPTIVE_TAB_SPECS]

    def _parse_adaptive_response(self, content: str) -> Dict[str, Any]:
        if not content or not str(content).strip():
            return {"summary": "", "tabs": self._default_adaptive_tabs()}
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return {"summary": "", "tabs": self._default_adaptive_tabs()}
            summary = str(parsed.get("summary") or "").strip()
            tabs = self._normalise_adaptive_tabs(parsed.get("tabs"))
            return {"summary": summary, "tabs": tabs}
        except Exception as exc:
            logger.warning("Failed to parse adaptive response: %s", exc, exc_info=True)
            return {"summary": "", "tabs": self._default_adaptive_tabs()}

    def _heuristic_framework(self, text: str, categories: List[FrameworkCategory]) -> Dict[str, Any]:
        segments = split_text_into_segments(text, max_chars=800)
        result_categories = []
        for cat in categories:
            snippets = [seg.text for seg in segments if any(keyword in seg.text for keyword in cat.title.split("/"))]
            items = []
            for snippet in snippets[:5]:
                items.append(
                    {
                        "title": cat.title,
                        "description": snippet[:200],
                        "evidence": snippet[:400],
                        "recommendation": "",
                        "severity": cat.severity,
                    }
                )
            result_categories.append({"id": cat.id, "title": cat.title, "items": items, "summary": cat.description})
        return {"categories": result_categories, "timeline": {"milestones": [], "remark": ""}, "raw_response": "heuristic"}

    def _call_openai_framework(
        self,
        text: str,
        categories: List[FrameworkCategory],
    ) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key")
        if not api_key:
            raise RuntimeError("缺少 OpenAI API key")
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        model = self.model or self.options.get("model") or "gpt-4o-mini"
        prompt = self._build_framework_prompt(text, categories)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是投标标书分析专家，必须按要求返回 JSON，禁止虚构。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                proxies=self._no_proxy,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = self._parse_framework_response(content)
            result.setdefault("raw_response", content)
            return result
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.warning("LLM HTTPError (%s): %s", exc, body)
            fallback = self._heuristic_framework(text, categories)
            fallback.setdefault("raw_response", body)
            return fallback

    def _call_azure_framework(
        self,
        text: str,
        categories: List[FrameworkCategory],
    ) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests 库未安装，无法调用 Azure OpenAI 接口")
        api_key = self.api_key or self.options.get("api_key") or self.options.get("key")
        endpoint = self.base_url or self.options.get("endpoint")
        deployment = self.options.get("deployment") or self.model
        if not (api_key and endpoint and deployment):
            raise RuntimeError("Azure OpenAI 配置缺失 (api_key / endpoint / deployment)")
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version=2023-07-01-preview"
        prompt = self._build_framework_prompt(text, categories)
        payload = {
            "messages": [
                {"role": "system", "content": "你是投标标书分析专家，必须按要求返回 JSON，禁止虚构。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout, proxies=self._no_proxy)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = self._parse_framework_response(content)
            result.setdefault("raw_response", content)
            return result
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.warning("Azure LLM HTTPError (%s): %s", exc, body)
            fallback = self._heuristic_framework(text, categories)
            fallback.setdefault("raw_response", body)
            return fallback

    def _build_framework_prompt(self, text: str, categories: List[FrameworkCategory]) -> str:
        framework = [
            {
                "id": cat.id,
                "title": cat.title,
                "description": cat.description,
                "default_severity": cat.severity,
            }
            for cat in categories
        ]

        payload = {
            "task": "tender_overview",
            "instructions": (
                "仔细阅读 document，从 framework 的视角总结投标要点。"
                " 对每个类别输出 summary 与 0-6 条 items。"
                " 每个 item 需包含 title、description、evidence、recommendation（可空）、severity。"
                " severity 必须是 critical/high/medium/low 中之一，可结合 default_severity。"
                " evidence 必须引用原文或复述原文关键字段。"
                " 同时输出 timeline，包含 milestones（数组，元素为 {name, deadline, note}）与 remark。"
                " 全部内容仅能依据 document，严禁杜撰。最终仅返回 JSON：{\"categories\":[...],\"timeline\":{...}}。"
            ),
            "framework": framework,
            "document": text[:20000],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _parse_framework_response(self, content: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return {"categories": [], "timeline": {"milestones": [], "remark": ""}, "raw_response": content}
            categories = parsed.get("categories") or []
            timeline = parsed.get("timeline") or {}
            if not isinstance(categories, list):
                categories = []
            normalized_categories = []
            for cat in categories:
                if not isinstance(cat, dict):
                    continue
                items = cat.get("items") or []
                if isinstance(items, dict):
                    items = [items]
                normalized_items = []
                for item in items:
                    if isinstance(item, dict):
                        normalized_items.append(
                            {
                                "title": str(item.get("title") or item.get("name") or "").strip(),
                                "description": str(item.get("description") or item.get("detail") or "").strip(),
                                "evidence": str(item.get("evidence") or item.get("source") or "").strip(),
                                "recommendation": str(item.get("recommendation") or item.get("advice") or "").strip(),
                                "severity": (item.get("severity") or item.get("level") or "medium").lower(),
                            }
                        )
                    else:
                        text_item = str(item).strip()
                        if text_item:
                            normalized_items.append(
                                {
                                    "title": text_item,
                                    "description": text_item,
                                    "evidence": text_item,
                                    "recommendation": "",
                                    "severity": "medium",
                                }
                            )
                normalized_categories.append(
                    {
                        "id": cat.get("id"),
                        "title": cat.get("title"),
                        "summary": cat.get("summary") or cat.get("overview") or "",
                        "items": normalized_items,
                    }
                )
            if isinstance(timeline, list):
                timeline = {"milestones": timeline, "remark": ""}
            elif isinstance(timeline, dict):
                milestones = timeline.get("milestones") or timeline.get("items") or []
                if isinstance(milestones, dict):
                    milestones = [milestones]
                normalized_milestones = []
                for m in milestones:
                    if isinstance(m, dict):
                        normalized_milestones.append(
                            {
                                "name": str(m.get("name") or m.get("title") or "").strip(),
                                "deadline": str(m.get("deadline") or m.get("date") or "").strip(),
                                "note": str(m.get("note") or m.get("description") or "").strip(),
                            }
                        )
                    else:
                        text_m = str(m).strip()
                        if text_m:
                            normalized_milestones.append({"name": text_m, "deadline": "", "note": ""})
                timeline = {
                    "milestones": normalized_milestones,
                    "remark": timeline.get("remark") or timeline.get("summary") or "",
                }
            else:
                timeline = {"milestones": [], "remark": ""}
            return {"categories": normalized_categories, "timeline": timeline, "raw_response": content}
        except Exception as exc:
            logger.warning("Failed to parse framework response: %s", exc, exc_info=True)
            return {"categories": [], "timeline": {"milestones": [], "remark": ""}, "raw_response": content}

    def _heuristic_adaptive(self, text: str) -> Dict[str, Any]:
        snippet = (text or "")[:200].strip()
        total_len = len(text or "")
        tabs: List[Dict[str, Any]] = []
        for tab_id, title in ADAPTIVE_TAB_SPECS:
            items: List[Dict[str, Any]] = []
            if snippet and tab_id == "hard_requirements":
                items.append(
                    {
                        "title": "请人工核对硬性要求",
                        "why_important": "自动分析失败，启发式仅提供原文开头片段，请人工核查是否存在废标风险。",
                        "guidance": "逐条核对资质、保证金、关键节点等硬性条款，必要时组织复核。",
                        "priority": "medium",
                        "source_excerpt": snippet,
                        "source_start": 0,
                        "source_end": min(len(snippet), total_len),
                    }
                )
            tabs.append({"id": tab_id, "title": title, "items": items})
        return {"summary": "自动摘要失败，以下为启发式抽取结果。", "tabs": tabs, "raw_response": "heuristic"}
