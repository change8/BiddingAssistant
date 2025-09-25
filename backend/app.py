from __future__ import annotations

import io
import json
import os
from typing import Any, Dict, List, Optional

try:
    from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except Exception:
    # Allow reading code without FastAPI installed
    FastAPI = object  # type: ignore
    UploadFile = object  # type: ignore
    File = lambda *args, **kwargs: None  # type: ignore
    HTTPException = Exception  # type: ignore
    JSONResponse = dict  # type: ignore
    BackgroundTasks = object  # type: ignore
    Query = lambda *args, **kwargs: None  # type: ignore
    StaticFiles = object  # type: ignore
    FileResponse = dict  # type: ignore

from .models import AnalyzeRequest
from .analyzer.llm import LLMClient
from .analyzer.framework import DEFAULT_FRAMEWORK
from .analyzer.tender_llm import TenderLLMAnalyzer
from .config import AppConfig, load_config
from .services.analyzer_service import AnalysisService, background_runner

try:
    import yaml
except Exception:
    yaml = None


def create_app(rules_path: str = None, config_path: str = None):  # type: ignore
    config = load_config(config_path)
    llm = LLMClient(**config.llm.as_kwargs())
    analyzer = TenderLLMAnalyzer(llm, categories=DEFAULT_FRAMEWORK)
    service = AnalysisService(analyzer)

    if FastAPI is object:
        return None  # FastAPI not installed; return sentinel

    app = FastAPI(title="投标助手 API", version="0.1.0")

    web_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "web")
    web_dir = os.path.abspath(web_dir)
    if os.path.isdir(web_dir) and StaticFiles is not object:
        app.mount("/web/static", StaticFiles(directory=web_dir), name="web-static")

        @app.get("/web")
        def web_index():
            index_path = os.path.join(web_dir, "index.html")
            if not os.path.exists(index_path):
                raise HTTPException(status_code=404, detail="web 前端未构建")
            return FileResponse(index_path)

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

    @app.get("/jobs/{job_id}/source")
    def get_job_source(
        job_id: str,
        start: int = Query(..., ge=0, description="原文字符起始位置"),
        end: Optional[int] = Query(None, description="原文字符结束位置（可选）"),
        window: int = Query(120, ge=0, le=2000, description="上下文窗口大小"),
    ):
        try:
            payload = service.get_source_snippet(job_id, start=start, end=end, window=window)
        except KeyError:
            raise HTTPException(status_code=404, detail="job 不存在或未保留原文")
        return JSONResponse(payload)

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
