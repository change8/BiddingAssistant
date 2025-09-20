from __future__ import annotations

import io
import json
import os
from typing import Any, Dict, List, Optional

try:
    from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
    from fastapi.responses import JSONResponse
except Exception:
    # Allow reading code without FastAPI installed
    FastAPI = object  # type: ignore
    UploadFile = object  # type: ignore
    File = lambda *args, **kwargs: None  # type: ignore
    HTTPException = Exception  # type: ignore
    JSONResponse = dict  # type: ignore
    BackgroundTasks = object  # type: ignore
    Query = lambda *args, **kwargs: None  # type: ignore

from .models import AnalyzeRequest
from .analyzer.llm import LLMClient
from .analyzer.retrieval import EmbeddingRetriever, HeuristicRetriever, merge_retrievals
from .analyzer.rules_engine import Rule, RulesEngine
from .config import AppConfig, load_config
from .services.analyzer_service import AnalysisService, background_runner

try:
    import yaml
except Exception:
    yaml = None


def load_rules(path: str) -> List[Rule]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            data = json.load(f)
        else:
            if yaml is None:
                raise RuntimeError("YAML not available to parse rules")
            data = yaml.safe_load(f)
    rules: List[Rule] = []
    for item in data.get("rules", []):
        rules.append(
            Rule(
                id=item["id"],
                category=item["category"],
                description=item.get("description", ""),
                match_type=item.get("match_type", "keyword"),
                patterns=item.get("patterns", []),
                severity=item.get("severity", "medium"),
                advice=item.get("advice"),
            )
        )
    return rules


def _build_retriever(cfg: AppConfig):
    retrievers = []
    if cfg.retrieval.enable_heuristic:
        retrievers.append(HeuristicRetriever(limit=cfg.retrieval.limit))
    if cfg.retrieval.enable_embedding:
        retrievers.append(EmbeddingRetriever(model_name=cfg.retrieval.embedding_model or "shibing624/text2vec-base-chinese", limit=cfg.retrieval.limit))
    return merge_retrievals(*retrievers)


def create_app(rules_path: str = None, config_path: str = None):  # type: ignore
    rules_path = rules_path or os.path.join(os.path.dirname(__file__), "rules", "checklist.zh-CN.yaml")
    rules = load_rules(rules_path)
    config = load_config(config_path)
    llm = LLMClient(**config.llm.as_kwargs())
    retriever = _build_retriever(config)
    engine = RulesEngine(rules, llm=llm, retriever=retriever)
    service = AnalysisService(engine)

    if FastAPI is object:
        return None  # FastAPI not installed; return sentinel

    app = FastAPI(title="投标助手 API", version="0.1.0")

    @app.get("/config")
    def get_config():
        cfg = {
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "base_url": config.llm.base_url,
                "timeout": config.llm.timeout,
            },
            "retrieval": {
                "enable_heuristic": config.retrieval.enable_heuristic,
                "enable_embedding": config.retrieval.enable_embedding,
                "embedding_model": config.retrieval.embedding_model,
                "limit": config.retrieval.limit,
            },
        }
        return cfg

    @app.get("/rules")
    def get_rules():
        return {"rules": [r.__dict__ for r in rules]}

    @app.post("/analyze/text")
    async def analyze_text(req: AnalyzeRequest, background_tasks: BackgroundTasks):
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="text 不能为空")

        async_runner = None
        if getattr(req, "async_mode", False):
            async_runner = lambda func, *args, **kwargs: background_runner(background_tasks, func, *args, **kwargs)

        job = service.submit_text(
            text=text,
            filename=req.filename,
            metadata=req.metadata,
            async_runner=async_runner,
        )
        include_result = not getattr(req, "async_mode", False)
        return JSONResponse(service.serialize_job(job.job_id, include_result=include_result))

    @app.post("/analyze/file")
    async def analyze_file(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        async_mode: bool = Query(False),
        filename: Optional[str] = Query(None),
    ):
        if file is UploadFile:
            raise HTTPException(status_code=500, detail="当前环境未安装 FastAPI 上传依赖")

        file_name = filename or getattr(file, "filename", None)
        content_type = getattr(file, "content_type", None)
        file_bytes = await file.read()
        buffer = io.BytesIO(file_bytes)
        metadata = {"content_type": content_type} if content_type else {}

        async_runner = None
        if async_mode:
            async_runner = lambda func, *args, **kwargs: background_runner(background_tasks, func, *args, **kwargs)

        job = service.submit_file(
            buffer,
            filename=file_name,
            content_type=content_type,
            metadata=metadata,
            async_runner=async_runner,
        )
        return JSONResponse(service.serialize_job(job.job_id, include_result=not async_mode))

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        try:
            return JSONResponse(service.serialize_job(job_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="job 不存在")

    @app.get("/jobs")
    def list_jobs():
        return JSONResponse(service.list_jobs())

    @app.delete("/jobs/{job_id}")
    def delete_job(job_id: str):
        removed = service.delete_job(job_id)
        if not removed:
            raise HTTPException(status_code=404, detail="job 不存在")
        return {"ok": True}

    return app


if __name__ == "__main__":
    # Optional: uvicorn entry (requires extra install)
    try:
        import uvicorn  # type: ignore

        uvicorn.run(create_app(), host="0.0.0.0", port=8000)
    except Exception:
        print("FastAPI/uvicorn 未安装，跳过本地运行。")
