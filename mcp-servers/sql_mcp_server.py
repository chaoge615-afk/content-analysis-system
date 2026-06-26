"""SQL MCP Server (port 9003/sse)

将 text-to-sql REST API 封装为 MCP 工具：
- text_to_sql: 自然语言 → SQL 查询
- get_tables: 获取数据库表结构
"""
import os
import json

import httpx
from mcp.server.fastmcp import FastMCP

SQL_SERVICE_URL = os.getenv("SQL_SERVICE_URL", "http://localhost:8010")
# CS-45：底层 text-to-sql pipeline 单次 run 实测 157-342s（首问/重试场景），
# 60s 默认必超时（httpx.ReadTimeout 先于底层完成抛出）。默认抬到 300s，
# docker-compose 生产环境注入 SQL_TIMEOUT=360 留余量。
REQUEST_TIMEOUT = float(os.getenv("SQL_TIMEOUT", "300"))

mcp = FastMCP(
    "SQL MCP Server",
    instructions="Bilibili 视频数据库结构化查询服务。将自然语言转换为 SQL 并执行查询。",
    host="0.0.0.0",
    port=9003,
)


@mcp.tool()
async def text_to_sql(question: str, filters: dict | None = None) -> str:
    """将自然语言问题转换为 SQL 查询，从 Bilibili 视频数据库中获取结构化数据。

    适用场景：统计、计数、排名、时间范围查询、特定UP主的视频数据等。

    Args:
        question: 自然语言问题，如"桃姐有多少个视频"、"播放量最高的10个视频"
        filters: 可选过滤条件，如 {"up_name": "桃姐", "category": "恋爱技巧"}
    """
    # 将过滤条件注入问题文本（与 router-agent 的 query_dispatcher 逻辑一致）
    enhanced_question = question
    if filters:
        hints = []
        if filters.get("up_name"):
            hints.append(f"（UP主完整名称是：{filters['up_name']}）")
        if filters.get("category"):
            hints.append(f"（分类名：{filters['category']}）")
        if hints:
            enhanced_question = f"{question} {' '.join(hints)}"

    payload = {"question": enhanced_question}
    if filters:
        payload["pre_intent"] = {"filters": filters}

    try:
        # CS-45：用结构化 Timeout，连接快失败、读慢可等，避免连接阶段也吃满超时
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=REQUEST_TIMEOUT, write=10.0, pool=10.0)
        ) as client:
            resp = await client.post(
                f"{SQL_SERVICE_URL}/query",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            # 构建返回结果
            if data.get("success"):
                result = {
                    "success": True,
                    "answer": data.get("answer", ""),
                    "sql": data.get("sql"),
                    "data": data.get("result", []),
                }
            else:
                result = {
                    "success": False,
                    "error": data.get("error", "查询失败"),
                    "sql": data.get("sql"),
                }
            return json.dumps(result, ensure_ascii=False)

    except httpx.ConnectError:
        return json.dumps(
            {"success": False, "error": "Text-to-SQL 服务不可用"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"SQL 查询异常: {str(e)}"},
            ensure_ascii=False,
        )


@mcp.tool()
async def get_tables() -> str:
    """获取 Bilibili 视频数据库的所有表结构信息。

    返回表名、字段名、字段类型等，帮助理解数据库结构。
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{SQL_SERVICE_URL}/api/tables")
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(data, ensure_ascii=False)
    except httpx.ConnectError:
        return json.dumps(
            {"success": False, "error": "Text-to-SQL 服务不可用", "tables": []},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"获取表结构失败: {str(e)}", "tables": []},
            ensure_ascii=False,
        )


def run():
    """启动 SQL MCP Server"""
    print(f"[SQL MCP] 连接 text-to-sql: {SQL_SERVICE_URL}")
    mcp.run(transport="sse")


if __name__ == "__main__":
    run()
