"""Bilibili MCP Server (port 9001/sse)

占位实现 — bilibili-monitor 是批处理服务，不直接提供实时查询。
暴露一个信息工具，说明服务状态。
"""
import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Bilibili MCP Server",
    instructions="Bilibili 视频数据采集服务（批处理模式）。视频数据通过定时任务自动采集到数据库。",
    host="0.0.0.0",
    port=9001,
)


@mcp.tool()
async def get_monitor_info() -> str:
    """获取 Bilibili 视频监控服务的状态信息。

    bilibili-monitor 是批处理服务，通过定时任务自动采集视频数据。
    采集的数据存入 DuckDB（结构化）和 ChromaDB（向量化），
    可通过 text_to_sql 和 semantic_search 工具查询。
    """
    return json.dumps(
        {
            "service": "bilibili-monitor",
            "mode": "batch_cron",
            "status": "running",
            "description": "Bilibili 视频自动采集 + 转写 + 精炼（定时任务）",
            "data_access": "通过 text_to_sql（结构化查询）或 semantic_search（语义检索）访问已采集数据",
        },
        ensure_ascii=False,
    )


def run():
    """启动 Bilibili MCP Server"""
    print("[Bilibili MCP] 占位服务启动")
    mcp.run(transport="sse")


if __name__ == "__main__":
    run()
