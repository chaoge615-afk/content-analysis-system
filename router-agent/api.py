"""
Router Agent - FastAPI 服务
统一入口：意图识别 + 查询分发 + 结果融合
"""

import time
import sys
from pathlib import Path

# 确保 src 可导入
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import concurrent.futures

from src.config import PORT, HOST
from src.intent_classifier import IntentClassifier
from src.query_dispatcher import QueryDispatcher
from src.result_merger import ResultMerger
from src.query_logger import QueryLogger

# ============ FastAPI 应用 ============
app = FastAPI(title="Router Agent", version="1.0.0", description="智能内容分析系统统一入口")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 全局组件 ============
classifier = IntentClassifier()
dispatcher = QueryDispatcher()
merger = ResultMerger()
query_logger = QueryLogger()


# ============ 请求/响应模型 ============

class ChatRequest(BaseModel):
    question: str
    force_route: Optional[str] = None  # 强制路由: "sql" | "rag" | None(自动)


class ChatResponse(BaseModel):
    answer: str
    route_type: str  # "structured" | "semantic" | "hybrid"
    sql: Optional[str] = None
    sql_result: Optional[list] = None
    sources: Optional[list] = None
    reasoning: Optional[str] = None
    response_time: Optional[float] = None


# ============ 核心问答接口 ============

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    统一问答入口

    流程：
    1. 意图分类（或强制路由）
    2. 分发到对应子系统
    3. hybrid 模式并行查询 + LLM 融合
    """
    start_time = time.time()
    question = req.question.strip()

    if not question:
        return ChatResponse(answer="请输入问题", route_type="semantic")

    # Step 1: 意图分类
    if req.force_route:
        intent = {
            "route_type": req.force_route,
            "filters": {},
            "reasoning": f"强制路由到 {req.force_route}",
        }
    else:
        intent = classifier.classify(question)

    route_type = intent["route_type"]
    filters = intent.get("filters", {})
    reasoning = intent.get("reasoning", "")

    # Step 2: 分发查询
    if route_type == "structured":
        sql_result = dispatcher.query_sql(question, filters=filters)
        answer = sql_result.get("answer") or sql_result.get("error", "查询无结果")
        elapsed = time.time() - start_time

        # 记录查询日志
        query_logger.log(question, "structured", elapsed)

        return ChatResponse(
            answer=answer,
            route_type="structured",
            sql=sql_result.get("sql"),
            sql_result=sql_result.get("result"),
            reasoning=reasoning,
            response_time=round(elapsed, 2),
        )

    elif route_type == "semantic":
        rag_result = dispatcher.query_rag(question, filters=filters)
        answer = rag_result.get("answer", "未找到相关内容")
        elapsed = time.time() - start_time

        # 记录查询日志
        query_logger.log(question, "semantic", elapsed)

        return ChatResponse(
            answer=answer,
            route_type="semantic",
            sources=rag_result.get("sources", []),
            reasoning=reasoning,
            response_time=round(elapsed, 2),
        )

    else:  # hybrid
        # 并行调用 SQL + RAG
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            sql_future = executor.submit(dispatcher.query_sql, question, filters)
            rag_future = executor.submit(dispatcher.query_rag, question, filters)

            sql_result = sql_future.result()
            rag_result = rag_future.result()

        # LLM 融合结果
        answer = merger.merge(question, sql_result, rag_result)
        elapsed = time.time() - start_time

        # 记录查询日志
        query_logger.log(question, "hybrid", elapsed)

        return ChatResponse(
            answer=answer,
            route_type="hybrid",
            sql=sql_result.get("sql"),
            sql_result=sql_result.get("result"),
            sources=rag_result.get("sources", []),
            reasoning=reasoning,
            response_time=round(elapsed, 2),
        )


# ============ 辅助接口 ============

@app.get("/api/status")
async def get_status():
    """系统状态（各子系统可用性）"""
    sql_health = dispatcher.check_sql_health()
    rag_health = dispatcher.check_rag_health()

    return {
        "router": "ok",
        "text_to_sql": "ok" if sql_health else "unavailable",
        "rag": "ok" if rag_health else "unavailable",
        "sql_url": dispatcher.sql_url,
        "rag_url": dispatcher.rag_url,
    }


@app.get("/api/up_list")
async def get_up_list():
    """UP 主列表（从 DuckDB up_info 表读取）"""
    try:
        result = dispatcher.query_sql("列出所有UP主及其视频数量")
        if result.get("success"):
            return {"success": True, "data": result.get("result", [])}
        return {"success": False, "error": result.get("error", "查询失败"), "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


@app.get("/api/recent")
async def get_recent():
    """最近采集视频（从 DuckDB video_meta 表读取）"""
    try:
        result = dispatcher.query_sql("最近采集的10个视频")
        if result.get("success"):
            return {"success": True, "data": result.get("result", [])}
        return {"success": False, "error": result.get("error", "查询失败"), "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


@app.get("/api/categories")
async def get_categories():
    """分类列表（31个情感分类 + 对应视频数）"""
    try:
        result = dispatcher.query_sql("各分类的视频数量统计")
        if result.get("success"):
            return {"success": True, "data": result.get("result", [])}
        return {"success": False, "error": result.get("error", "查询失败"), "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


# ============ 健康检查 ============

@app.get("/")
async def root():
    return {"status": "ok", "service": "Router Agent"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/query_stats")
async def get_query_stats():
    """查询统计（最近查询记录 + 总体统计）"""
    try:
        stats = query_logger.get_stats()
        recent = query_logger.get_recent(limit=10)
        return {
            "success": True,
            "stats": stats,
            "recent_queries": [
                {
                    "id": r[0],
                    "question": r[1],
                    "route_type": r[2],
                    "response_time": float(r[3]) if r[3] else 0,
                    "created_at": str(r[4]),
                }
                for r in recent
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
