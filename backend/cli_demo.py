# 简易 CLI 演示：对 sample_data 文本做规则匹配（不调用 LLM）

import os
import sys
import json

CUR = os.path.dirname(__file__)
ROOT = os.path.dirname(CUR)

sys.path.append(ROOT)

from analyzer.preprocess import preprocess_text
from analyzer.rules_engine import RulesEngine, Rule
from analyzer.llm import LLMClient
from analyzer.retrieval import EmbeddingRetriever, HeuristicRetriever, merge_retrievals
from config import load_config

try:
    import yaml
except Exception:
    yaml = None


def load_rules(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) if path.endswith(".yaml") and yaml else json.load(f)
    rules = [
        Rule(
            id=i["id"],
            category=i["category"],
            description=i.get("description", ""),
            match_type=i.get("match_type", "keyword"),
            patterns=i.get("patterns", []),
            severity=i.get("severity", "medium"),
            advice=i.get("advice"),
        )
        for i in data.get("rules", [])
    ]
    return rules


def main():
    sample = os.path.join(ROOT, "sample_data", "sample_tender.txt")
    with open(sample, "r", encoding="utf-8") as f:
        text = f.read()

    rules_path = os.path.join(CUR, "rules", "checklist.zh-CN.yaml")
    rules = load_rules(rules_path)

    config = load_config()
    llm = LLMClient(**config.llm.as_kwargs())
    retriever = merge_retrievals(
        HeuristicRetriever(limit=config.retrieval.limit) if config.retrieval.enable_heuristic else None,
        EmbeddingRetriever(model_name=config.retrieval.embedding_model or "shibing624/text2vec-base-chinese", limit=config.retrieval.limit)
        if config.retrieval.enable_embedding
        else None,
    )
    engine = RulesEngine(rules, llm=llm, retriever=retriever)
    cleaned, _ = preprocess_text(text)
    res = engine.analyze(cleaned)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
