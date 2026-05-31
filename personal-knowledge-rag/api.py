"""
视频知识库RAG - FastAPI 后端
提供视频知识库问答接口
"""

import warnings
warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import os

from rag_engine import KnowledgeRAG

# 初始化 FastAPI 应用
app = FastAPI(title="视频知识库问答系统", version="2.0.0")

# CORS middleware（供 Router Agent 跨服务调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取当前目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 全局 RAG 实例
rag_instance: Optional[KnowledgeRAG] = None


def get_rag() -> KnowledgeRAG:
    """获取或初始化 RAG 实例"""
    global rag_instance
    if rag_instance is None:
        rag_instance = KnowledgeRAG()
    return rag_instance


# ========== 请求/响应模型 ==========

class AskVideoRequest(BaseModel):
    """视频知识库问答请求"""
    question: str
    filters: Optional[dict] = None  # { up_name, category, bvid }
    use_hybrid: bool = True  # 是否使用 BM25+向量混合检索


class AskGenericRequest(BaseModel):
    """通用问答请求"""
    question: str
    collection: str = "video_knowledge"
    filters: Optional[dict] = None


# ========== 启动 ==========

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化 RAG"""
    try:
        get_rag()
        print("RAG 引擎初始化完成")
    except Exception as e:
        print(f"RAG 引擎初始化失败: {e}")


# ========== 页面 ==========

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    html_path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ========== 问答接口 ==========

@app.post("/api/ask_video")
async def ask_video(req: AskVideoRequest):
    """
    视频知识库问答（支持 metadata 过滤 + 混合检索）

    请求示例:
    {
        "question": "博主们对冷暴力怎么看？",
        "filters": {"up_name": "桃姐", "category": "01_喜欢"},
        "use_hybrid": true
    }
    """
    if not req.question or not req.question.strip():
        return {"answer": "请输入问题", "route_type": "semantic", "sources": []}

    try:
        rag = get_rag()
        answer, sources = rag.ask_video(
            req.question,
            metadata_filter=req.filters,
            use_hybrid=req.use_hybrid,
            return_sources=True,
        )
        return {
            "answer": answer,
            "route_type": "semantic",
            "sources": sources,
        }
    except Exception as e:
        return {
            "answer": f"处理问题时出错: {str(e)}",
            "route_type": "semantic",
            "sources": [],
        }


@app.post("/api/ask_generic")
async def ask_generic(req: AskGenericRequest):
    """
    通用问答接口（可指定 collection）
    Router Agent 统一调用入口
    """
    if not req.question or not req.question.strip():
        return {"answer": "请输入问题", "collection": req.collection}

    try:
        rag = get_rag()
        answer = rag.ask(
            req.question,
            collection=req.collection,
            metadata_filter=req.filters,
        )
        return {"answer": answer, "collection": req.collection}
    except Exception as e:
        return {"answer": f"处理问题时出错: {str(e)}", "collection": req.collection}


# ========== 统计 & 管理 ==========

@app.get("/api/stats")
async def get_stats():
    """获取知识库状态（含 video_knowledge 统计）"""
    try:
        rag = get_rag()
        stats = rag.get_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/collections")
async def get_collections():
    """返回所有 collection 信息"""
    try:
        rag = get_rag()
        collections = rag.get_collections()
        return {"success": True, "collections": collections}
    except Exception as e:
        return {"success": False, "error": str(e), "collections": []}


@app.post("/api/load_video")
async def load_video_knowledge():
    """触发视频知识库加载（video_knowledge collection）"""
    try:
        rag = get_rag()
        count = rag.load_video_knowledge()
        return {"success": True, "chunks_loaded": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/clear_video")
async def clear_video_knowledge():
    """清空视频知识库"""
    try:
        rag = get_rag()
        rag.clear_database("video_knowledge")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== 健康检查 ==========

@app.get("/health")
async def health():
    """健康检查"""
    try:
        rag = get_rag()
        stats = rag.get_stats()
        return {"status": "ok", "stats": stats}
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8090)
