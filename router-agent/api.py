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

from fastapi import FastAPI, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import concurrent.futures

from src.config import PORT, HOST
from src.intent_classifier import IntentClassifier
from src.query_dispatcher import QueryDispatcher
from src.result_merger import ResultMerger
from src.query_logger import QueryLogger
from src.monitor_trigger import MonitorTrigger
from src.up_manager import UpManager
from src.asr_manager import AsrManager
from src.up_export import UpExporter

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
up_manager = UpManager()
asr_manager = AsrManager()
up_exporter = UpExporter()

# DuckDB 只读连接（每次创建新连接，避免跨容器锁冲突）

def _get_db():
    """获取 DuckDB 只读连接（每次调用创建新连接）"""
    import duckdb as _duckdb
    db_path = os.getenv("DUCKDB_PATH", "data/content.db")
    return _duckdb.connect(db_path, read_only=True)


# ============ 请求/响应模型 ============

class ChatRequest(BaseModel):
    question: str
    force_route: Optional[str] = None  # 强制路由: "sql" | "rag" | None(自动)
    domain: Optional[str] = None  # 内容域: "emotional" | "career" | None(全部)


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


class CookieRequest(BaseModel):
    content: str  # Netscape 格式的 Cookie 内容


class AddUpRequest(BaseModel):
    url: str  # B站主页或视频链接
    whisper_model: Optional[str] = "small"  # Whisper 模型大小
    domain: Optional[str] = "emotional"  # 内容域: emotional | career


class UpdateUpRequest(BaseModel):
    whisper_model: Optional[str] = None  # 更新的 Whisper 模型


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
    error_hint = intent.get("error_hint", "")

    # 前端传入的 domain 注入到检索过滤条件
    if req.domain:
        filters["domain"] = req.domain

    # Step 2: 分发查询
    if route_type == "structured":
        sql_result = dispatcher.query_sql(question, filters=filters, intent=intent)
        answer = sql_result.get("answer") or sql_result.get("error", "查询无结果")
        if error_hint:
            answer = f"{error_hint}\n\n{answer}"
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
        if error_hint:
            answer = f"{error_hint}\n\n{answer}"
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
            sql_future = executor.submit(dispatcher.query_sql, question, filters, intent)
            rag_future = executor.submit(dispatcher.query_rag, question, filters)

            sql_result = sql_future.result()
            rag_result = rag_future.result()

        # LLM 融合结果
        answer = merger.merge(question, sql_result, rag_result)
        if error_hint:
            answer = f"{error_hint}\n\n{answer}"
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
        conn = _get_db()
        try:
            # 优先从 up_info 表读取
            up_count = conn.execute("SELECT COUNT(*) FROM up_info").fetchone()[0]
            if up_count > 0:
                rows = conn.execute(
                    "SELECT uid, name, total_videos, last_update FROM up_info ORDER BY total_videos DESC"
                ).fetchall()
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
            return {
                "success": True,
                "data": [
                    {"uid": "", "name": r[0], "total_videos": r[1], "last_update": None}
                    for r in rows
                ],
            }
        finally:
            conn.close()
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


# ============ UP主管理接口 ============

@app.get("/api/up_info/resolve")
async def resolve_up_url(url: str = Query(..., description="B站主页或视频链接")):
    """解析 B站链接，预览 UP主信息（不保存）"""
    parsed = up_manager.parse_url(url)
    if parsed["type"] == "invalid":
        return {"success": False, "error": "无效的链接格式，请提供 B站主页或视频链接"}

    profile = up_manager.fetch_profile(parsed)
    return profile


@app.get("/api/up_info")
async def list_ups():
    """列出所有已配置的 UP主（从 config/ 目录读取）"""
    ups = up_manager.list_ups()

    # 补充 DuckDB 中的视频数量
    try:
        conn = _get_db()
        try:
            for up in ups:
                uid = up["uid"]
                if uid:
                    count = conn.execute(
                        "SELECT COUNT(*) FROM video_meta WHERE up_uid = ?", [uid]
                    ).fetchone()[0]
                    up["video_count"] = count
                    up["has_video"] = count > 0
        finally:
            conn.close()
    except Exception:
        pass

    return {"success": True, "data": ups}


@app.post("/api/up_info")
async def add_up(req: AddUpRequest):
    """添加新 UP主（解析链接 → 获取信息 → 创建配置）"""
    result = up_manager.add_up(req.url, req.whisper_model or "small", req.domain or "emotional")
    return result


@app.delete("/api/up_info/{uid}")
async def remove_up(uid: str):
    """删除 UP主配置"""
    result = up_manager.remove_up(uid)
    return result


@app.get("/api/up_info/{uid}/export")
async def export_up(uid: str):
    """
    导出 UP主 完整数据为 ZIP 文件

    包含：配置、视频元数据、ChromaDB 向量、转写文本、检查点文件
    """
    try:
        zip_bytes = up_exporter.export_up(uid)
        filename = f"up_export_{uid}.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"导出失败: {e}"}


@app.post("/api/up_info/import")
async def import_up(
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
):
    """
    从 ZIP 文件导入 UP主 完整数据

    支持覆盖或跳过已有数据
    """
    try:
        zip_bytes = await file.read()
        result = up_exporter.import_up(zip_bytes, overwrite=overwrite)
        return result
    except Exception as e:
        return {"success": False, "error": f"导入失败: {e}"}


# ============ ASR 转写接口 ============

class AsrSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    monthly_budget_minutes: Optional[float] = None


@app.get("/api/asr/status")
async def get_asr_status():
    """获取 ASR 设置和用量状态"""
    return {"success": True, "data": asr_manager.get_status()}


@app.post("/api/asr/settings")
async def update_asr_settings(req: AsrSettingsRequest):
    """更新 ASR 设置"""
    data = {}
    if req.enabled is not None:
        data["enabled"] = req.enabled
    if req.monthly_budget_minutes is not None:
        data["monthly_budget_minutes"] = req.monthly_budget_minutes

    result = asr_manager.update_settings(data)
    return {"success": True, "data": result}


@app.post("/api/asr/transcribe")
async def trigger_asr_transcribe():
    """手动触发 ASR 转写（通过 Docker SDK 启动 bilibili-monitor --asr）"""
    # 检查预算
    budget_check = asr_manager.check_budget()
    if not budget_check["ok"]:
        return {
            "success": False,
            "error": budget_check["message"],
        }

    # 复用 MonitorTrigger 的容器启动逻辑，添加 --asr 参数
    params = {"asr": True}
    result = monitor_trigger.trigger(params)
    return result


@app.get("/api/recent")
async def get_recent():
    """最近采集视频（从 DuckDB video_meta 表读取）"""
    try:
        conn = _get_db()
        try:
            rows = conn.execute(
                """SELECT bvid, up_name, title, publish_date, category, duration
                   FROM video_meta
                   ORDER BY created_at DESC LIMIT 10"""
            ).fetchall()
            data = [
                {"bvid": r[0], "up_name": r[1], "title": r[2], "publish_date": str(r[3]) if r[3] else None, "category": r[4], "duration": r[5]}
                for r in rows
            ]
            return {"success": True, "data": data}
        finally:
            conn.close()
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


@app.get("/api/categories")
async def get_categories():
    """分类列表（31个情感分类 + 对应视频数）"""
    try:
        conn = _get_db()
        try:
            rows = conn.execute(
                """SELECT category, COUNT(*) as cnt
                   FROM video_meta
                   WHERE category IS NOT NULL AND category != ''
                   GROUP BY category
                   ORDER BY cnt DESC"""
            ).fetchall()
            data = [{"category": r[0], "count": r[1]} for r in rows]
            return {"success": True, "data": data}
        finally:
            conn.close()
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


# ============ Cookie 管理 ============

COOKIE_FILE = os.path.join(os.path.dirname(os.getenv("DUCKDB_PATH", "data/content.db")), "bilibili_cookie.txt")


@app.post("/api/cookie")
async def set_cookie(req: CookieRequest):
    """保存 Cookie（Netscape 格式内容写入共享卷）"""
    content = req.content.strip()
    if not content:
        return {"success": False, "error": "Cookie 内容不能为空"}

    # 基本校验：Netscape 格式至少包含 SESSDATA 或 DedeUserID
    if "SESSDATA" not in content and "DedeUserID" not in content:
        return {"success": False, "error": "Cookie 内容无效（缺少 SESSDATA 或 DedeUserID）"}

    try:
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "message": "Cookie 已保存"}
    except Exception as e:
        return {"success": False, "error": f"保存失败: {e}"}


@app.get("/api/cookie")
async def get_cookie_status():
    """Cookie 状态（是否已配置 + 来源）"""
    return monitor_trigger.check_cookie()


@app.delete("/api/cookie")
async def delete_cookie():
    """删除已保存的 Cookie"""
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
            return {"success": True, "message": "Cookie 已删除"}
        return {"success": True, "message": "Cookie 文件不存在（无需删除）"}
    except Exception as e:
        return {"success": False, "error": f"删除失败: {e}"}


@app.post("/api/cookie/test")
async def test_cookie_api():
    """测试 Cookie 有效性（调用 B站 API 验证）"""
    import re
    import requests as req

    # 读取 cookie 文件
    if not os.path.exists(COOKIE_FILE):
        return {"success": False, "valid": False, "error": "Cookie 文件不存在，请先保存"}

    try:
        with open(COOKIE_FILE, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return {"success": False, "valid": False, "error": f"读取文件失败: {e}"}

    # 解析 Netscape 格式
    needed_keys = {"SESSDATA", "bili_jct", "DedeUserID"}
    cookies = {}
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) >= 7:
            name = parts[5]
            if name in needed_keys:
                cookies[name] = parts[6]

    missing = needed_keys - set(cookies.keys())
    if missing:
        return {
            "success": False,
            "valid": False,
            "error": f"Cookie 缺少必需字段: {missing}",
        }

    # 调用 B站 API 验证
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    try:
        resp = req.get(
            "https://api.bilibili.com/x/web-interface/nav",
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        data = resp.json()
        code = data.get("code", 0)

        if code == 0:
            uname = data.get("data", {}).get("uname", "未知")
            mid = data.get("data", {}).get("mid", "")
            is_login = data.get("data", {}).get("isLogin", False)
            return {
                "success": True,
                "valid": True,
                "message": f"Cookie 有效，已登录用户: {uname} (mid: {mid})",
                "uname": uname,
                "mid": mid,
                "is_login": is_login,
            }
        elif code == -101:
            return {
                "success": True,
                "valid": False,
                "error": "Cookie 已过期或未登录，请重新获取",
                "code": code,
            }
        elif code == -352:
            return {
                "success": True,
                "valid": False,
                "error": "风控校验失败（Cookie 已过期或被风控）",
                "code": code,
            }
        else:
            return {
                "success": True,
                "valid": False,
                "error": f"B站 API 返回错误: {data.get('message', '未知')} (code={code})",
                "code": code,
            }
    except Exception as e:
        return {"success": False, "valid": False, "error": f"API 请求失败: {e}"}


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

        # 三路并行采集：Docker stats / RAG / DuckDB（避免串行等待）
        def _collect_containers():
            try:
                return monitor_trigger.get_container_metrics()
            except Exception as e:
                return {"_error": str(e)}

        def _collect_rag():
            try:
                rag_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8090")
                resp = req_lib.get(f"{rag_url}/api/stats", timeout=5)
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"HTTP {resp.status_code}"}
            except Exception as e:
                return {"error": str(e)}

        def _collect_sql():
            try:
                conn = _get_db()
                try:
                    table_names = conn.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
                    ).fetchall()
                    tables = []
                    for (tname,) in table_names:
                        try:
                            cnt = conn.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
                            tables.append({"table": tname, "count": cnt})
                        except Exception:
                            tables.append({"table": tname, "count": -1})
                    video_meta_cnt = conn.execute("SELECT COUNT(*) FROM video_meta").fetchone()[0]
                    return {"tables": tables, "total_videos": video_meta_cnt}
                finally:
                    conn.close()
            except Exception as e:
                return {"error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            f_containers = ex.submit(_collect_containers)
            f_rag = ex.submit(_collect_rag)
            f_sql = ex.submit(_collect_sql)
            metrics["containers"] = f_containers.result()
            metrics["rag_stats"] = f_rag.result()
            metrics["sql_stats"] = f_sql.result()

        # 4. 查询统计（纯内存，很快）
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
