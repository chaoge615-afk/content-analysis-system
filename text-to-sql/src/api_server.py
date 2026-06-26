"""FastAPI server for Text-to-SQL Multi-Agent System."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.pipeline import TextToSQLPipeline
from src.database.duckdb_utils import get_all_schemas, init_database

# 用 lifespan 替代已废弃的 @app.on_event("startup")（对抗审查修正建议 #4）
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # CS-09：容器启动即自举 schema/迁移，不再依赖 bilibili-monitor 是否跑过。
    # best-effort：失败不阻断 API 启动（init_database 内部已 try/except）。
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        init_database()
    except Exception as e:
        print(f"[api_server] init_database 警告: {e}")
    yield


app = FastAPI(title="Text-to-SQL API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize pipeline
pipeline = TextToSQLPipeline()


class QueryRequest(BaseModel):
    question: str
    pre_intent: Optional[dict] = None  # 来自 Router Agent 的预分类意图


class QueryResponse(BaseModel):
    success: bool
    sql: str | None = None
    result: list | None = None
    answer: str | None = None
    error: str | None = None
    iterations: int | None = None


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Handle query request."""
    try:
        result = pipeline.run(request.question, pre_intent=request.pre_intent)
        return QueryResponse(
            success=result.get("success", False),
            sql=result.get("sql"),
            result=result.get("result"),
            answer=result.get("answer"),
            error=result.get("error"),
            iterations=result.get("iterations"),
        )
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "error": f"服务暂时繁忙，请稍后重试。错误信息: {str(e)[:100]}",
                "sql": None,
                "result": None,
                "answer": None,
                "iterations": None,
            }
        )


@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "Text-to-SQL API"}


@app.get("/api/tables")
async def get_tables():
    """获取所有可用表及字段信息（供 Router Agent 使用）"""
    try:
        schemas = get_all_schemas()
        return {
            "success": True,
            "tables": schemas,
            "count": len(schemas)
        }
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "error": f"获取表信息失败: {str(e)}",
                "tables": [],
                "count": 0
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
