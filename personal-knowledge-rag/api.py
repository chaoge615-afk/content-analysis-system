"""
个人知识库RAG - FastAPI 后端
提供 Web 问答接口
"""
import warnings
warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os

from rag_engine import KnowledgeRAG

# 初始化 FastAPI 应用
app = FastAPI(title="个人知识库问答系统")

# 获取当前目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 全局 RAG 实例
rag_instance = None


def get_rag():
    """获取或初始化 RAG 实例"""
    global rag_instance
    if rag_instance is None:
        rag_instance = KnowledgeRAG()
    return rag_instance


class AskRequest(BaseModel):
    question: str


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化 RAG"""
    try:
        get_rag()
        print("RAG 引擎初始化完成")
    except Exception as e:
        print(f"RAG 引擎初始化失败: {e}")


@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    html_path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/ask")
async def ask_question(req: AskRequest):
    """处理问答请求"""
    if not req.question or not req.question.strip():
        return {"answer": "请输入问题"}

    try:
        rag = get_rag()
        answer = rag.ask(req.question)
        return {"answer": answer}
    except Exception as e:
        return {"answer": f"处理问题时出错: {str(e)}"}


@app.get("/api/stats")
async def get_stats():
    """获取知识库状态"""
    try:
        rag = get_rag()
        stats = rag.get_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/load")
async def load_knowledge():
    """触发知识库加载"""
    try:
        rag = get_rag()
        count = rag.load_knowledge()
        return {"success": True, "chunks_loaded": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/clear")
async def clear_knowledge():
    """清空知识库"""
    try:
        rag = get_rag()
        rag.clear_database()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="::", port=8090)
