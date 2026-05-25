"""
Router Agent - FastAPI 服务
统一入口：意图识别 + 查询分发 + 结果融合
"""

import os
import time
import sys
from pathlib import Path

# 确保 src 可导入
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import concurrent.futures

from src.config import PORT, HOST
from src.intent_classifier import IntentClassifier
from src.query_dispatcher import QueryDispatcher
from src.result_merger import ResultMerger
from src.query_logger import QueryLogger
from src.monitor_trigger import MonitorTrigger

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
monitor_trigger = MonitorTrigger()


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


class TriggerRequest(BaseModel):
    max_videos: Optional[int] = None   # 最大视频数限制
    up_names: Optional[list] = None    # 指定 UP 主列表（可选，多选）


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
    """UP 主列表（从 DuckDB 读取，优先 up_info，回退 video_meta 聚合）"""
    try:
        import duckdb as _duckdb
        db_path = os.getenv("DUCKDB_PATH", "data/content.db")
        conn = _duckdb.connect(db_path, read_only=True)

        # 优先从 up_info 表读取
        up_count = conn.execute("SELECT COUNT(*) FROM up_info").fetchone()[0]
        if up_count > 0:
            rows = conn.execute(
                "SELECT uid, name, total_videos, last_update FROM up_info ORDER BY total_videos DESC"
            ).fetchall()
            conn.close()
            return {
                "success": True,
                "data": [
                    {"uid": r[0], "name": r[1], "total_videos": r[2], "last_update": str(r[3]) if r[3] else None}
                    for r in rows
                ],
            }

        # up_info 为空时，从 video_meta 聚合
        rows = conn.execute(
            """SELECT up_name, COUNT(*) as cnt
               FROM video_meta
               WHERE up_name IS NOT NULL AND up_name != '' AND up_name != 'unknown'
               GROUP BY up_name
               ORDER BY cnt DESC"""
        ).fetchall()
        conn.close()
        return {
            "success": True,
            "data": [
                {"uid": "", "name": r[0], "total_videos": r[1], "last_update": None}
                for r in rows
            ],
        }
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
async def get_query_stats(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    route_type: Optional[str] = Query(None, description="按路由类型过滤"),
):
    """查询统计（分页查询记录 + 总体统计）"""
    try:
        stats = query_logger.get_stats()
        paginated = query_logger.get_paginated(
            page=page, page_size=page_size, route_type=route_type
        )
        return {
            "success": True,
            "stats": stats,
            "queries": paginated,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============ 采集触发接口 ============

@app.post("/api/trigger_monitor")
async def trigger_monitor(req: TriggerRequest):
    """触发 bilibili-monitor 采集任务"""
    params = {}
    if req.max_videos:
        params["max_videos"] = req.max_videos
    if req.up_names:
        params["up_names"] = req.up_names

    result = monitor_trigger.trigger(params)
    return result


@app.get("/api/trigger_status")
async def get_trigger_status():
    """获取采集任务状态"""
    return monitor_trigger.get_status()


# ============ 系统监控接口 ============

@app.get("/api/system_metrics")
async def get_system_metrics():
    """
    系统指标聚合
    - 容器资源使用（内存/CPU）
    - RAG 知识库统计
    - 数据库统计
    - 查询统计
    - 运行时间
    """
    import asyncio
    import requests as req_lib

    # 在线程池中执行阻塞操作，避免阻塞事件循环
    def _collect_metrics():
        metrics = {
            "uptime": monitor_trigger.get_uptime(),
            "containers": {},
            "rag_stats": {},
            "sql_stats": {},
            "query_stats": {},
        }

        # 1. 容器指标（Docker SDK）
        try:
            metrics["containers"] = monitor_trigger.get_container_metrics()
        except Exception as e:
            metrics["containers"] = {"_error": str(e)}

        # 2. RAG 统计
        try:
            rag_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8090")
            resp = req_lib.get(f"{rag_url}/api/stats", timeout=5)
            if resp.status_code == 200:
                metrics["rag_stats"] = resp.json()
        except Exception as e:
            metrics["rag_stats"] = {"error": str(e)}

        # 3. SQL/数据库统计（通过 Text-to-SQL 查询，使用短超时）
        try:
            sql_url = os.getenv("SQL_SERVICE_URL", "http://localhost:8010")
            resp = req_lib.post(
                f"{sql_url}/query",
                json={"question": "数据库各表的记录数量"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    metrics["sql_stats"] = {"tables": data.get("result", [])}
            # 视频总数
            resp2 = req_lib.post(
                f"{sql_url}/query",
                json={"question": "知识库一共有多少个视频"},
                timeout=15,
            )
            if resp2.status_code == 200:
                data2 = resp2.json()
                if data2.get("success") and data2.get("result"):
                    metrics["sql_stats"]["total_videos"] = data2["result"]
        except Exception as e:
            metrics["sql_stats"] = {"error": str(e)}

        # 4. 查询统计
        try:
            metrics["query_stats"] = query_logger.get_stats()
        except Exception as e:
            metrics["query_stats"] = {"error": str(e)}

        return metrics

    loop = asyncio.get_event_loop()
    metrics = await loop.run_in_executor(None, _collect_metrics)
    return metrics


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
