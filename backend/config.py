"""Configuration helpers for the bidding assistant backend."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


@dataclass
class LLMConfig:
    provider: str = "stub"
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    options: Dict[str, Any] = field(default_factory=dict)

    def as_kwargs(self) -> Dict[str, Any]:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "timeout": self.timeout,
        }
        payload.update(self.options)
        return {k: v for k, v in payload.items() if v is not None}


@dataclass
class RetrievalConfig:
    enable_heuristic: bool = True
    enable_embedding: bool = False
    embedding_model: Optional[str] = None
    limit: int = 6


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)


DEFAULT_CONFIG_PATHS = [
    os.getenv("BIDDING_ASSISTANT_CONFIG"),
    os.path.join(os.path.dirname(__file__), "config.yaml"),
    os.path.join(os.getcwd(), "config", "app.yaml"),
]


def load_config(config_path: Optional[str] = None) -> AppConfig:
    data: Dict[str, Any] = {}

    paths = [config_path] if config_path else DEFAULT_CONFIG_PATHS
    for path in paths:
        if not path:
            continue
        if not os.path.exists(path):
            continue
        data = _load_file(path)
        break

    # Environment overrides
    provider = os.getenv("BIDDING_ASSISTANT_LLM_PROVIDER", data.get("llm", {}).get("provider", "stub"))
    api_key = os.getenv("BIDDING_ASSISTANT_LLM_API_KEY", data.get("llm", {}).get("api_key"))
    base_url = os.getenv("BIDDING_ASSISTANT_LLM_BASE_URL", data.get("llm", {}).get("base_url"))
    model = os.getenv("BIDDING_ASSISTANT_LLM_MODEL", data.get("llm", {}).get("model"))
    timeout = int(os.getenv("BIDDING_ASSISTANT_LLM_TIMEOUT", data.get("llm", {}).get("timeout", 30)))
    options = data.get("llm", {}).get("options", {})

    llm_config = LLMConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        options=options,
    )

    retrieval_data = data.get("retrieval", {})
    retrieval_config = RetrievalConfig(
        enable_heuristic=retrieval_data.get("enable_heuristic", True),
        enable_embedding=retrieval_data.get("enable_embedding", False),
        embedding_model=retrieval_data.get("embedding_model"),
        limit=retrieval_data.get("limit", 6),
    )

    return AppConfig(llm=llm_config, retrieval=retrieval_config)


def _load_file(path: str) -> Dict[str, Any]:
    if path.endswith((".yaml", ".yml")):
        if yaml is None:
            raise RuntimeError("YAML configuration requested but PyYAML is not installed")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

