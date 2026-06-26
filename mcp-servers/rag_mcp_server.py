"""RAG MCP Server (port 9002/sse)

将 personal-knowledge-rag REST API 封装为 MCP 工具：
- semantic_search: 语义检索视频知识库
- get_stats: 获取知识库统计
"""
import os
import json

import httpx
from mcp.server.fastmcp import FastMCP

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8090")
REQUEST_TIMEOUT = float(os.getenv("RAG_TIMEOUT", "60"))

mcp = FastMCP(
    "RAG MCP Server",
    instructions="Bilibili 视频知识库语义检索服务。检索博主观点、经验分享等非结构化内容。",
    host="0.0.0.0",
    port=9002,
)


@mcp.tool()
async def semantic_search(
    question: str,
    filters: dict | None = None,
    top_k: int = None,
) -> str:
    """语义检索视频知识库，获取博主观点、经验分享等非结构化内容。

    适用场景：观点、建议、看法、经验分享、情感话题等需要语义理解的查询。

    Args:
        question: 自然语言问题，如"博主们对冷暴力怎么看"、"如何维持长期关系"
        filters: 可选过滤条件，如 {"up_name": "桃姐", "category": "恋爱技巧"}
        top_k: 返回结果数量；None 表示用 RAG 引擎 env TOP_K 默认（不覆盖），
               传入正整数则覆盖该次请求。默认 None 而非 5，避免走 MCP 路径时
               把 env TOP_K 静默覆盖回 5（CS-25 对抗审查修正）。
    """
    # top_k=None 时序列化为 null，api 层 Optional[int] 接收 None → engine 回退 env 默认
    payload = {
        "question": question,
        "filters": filters or {},
        "use_hybrid": True,
        "top_k": top_k,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{RAG_SERVICE_URL}/api/ask_video",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            result = {
                "success": True,
                "answer": data.get("answer", ""),
                "sources": data.get("sources", []),
                "route_type": data.get("route_type", "semantic"),
            }
            return json.dumps(result, ensure_ascii=False)

    except httpx.ConnectError:
        return json.dumps(
            {"success": False, "error": "RAG 服务不可用", "sources": []},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"RAG 查询异常: {str(e)}", "sources": []},
            ensure_ascii=False,
        )


@mcp.tool()
async def get_stats() -> str:
    """获取视频知识库的统计信息。

    返回知识库中的文档数量、collection 列表等。
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{RAG_SERVICE_URL}/api/stats")
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(data, ensure_ascii=False)
    except httpx.ConnectError:
        return json.dumps(
            {"error": "RAG 服务不可用"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"error": f"获取统计失败: {str(e)}"},
            ensure_ascii=False,
        )


def run():
    """启动 RAG MCP Server"""
    print(f"[RAG MCP] 连接 personal-knowledge-rag: {RAG_SERVICE_URL}")
    mcp.run(transport="sse")


if __name__ == "__main__":
    run()
