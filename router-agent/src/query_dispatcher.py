"""
查询分发模块
根据意图分类结果，将查询分发到 Text-to-SQL 或 RAG 服务
"""

import requests
from typing import Optional

from src.config import SQL_SERVICE_URL, RAG_SERVICE_URL, REQUEST_TIMEOUT


class QueryDispatcher:
    """查询分发器"""

    def __init__(self):
        self.sql_url = SQL_SERVICE_URL
        self.rag_url = RAG_SERVICE_URL
        self.timeout = REQUEST_TIMEOUT

    def query_sql(self, question: str) -> dict:
        """
        发送到 Text-to-SQL 服务

        Returns:
            {
                "success": bool,
                "sql": str | None,
                "result": list | None,
                "answer": str | None,
                "error": str | None
            }
        """
        try:
            resp = requests.post(
                f"{self.sql_url}/query",
                json={"question": question},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            return {
                "success": False,
                "error": "Text-to-SQL 服务不可用",
                "sql": None,
                "result": None,
                "answer": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Text-to-SQL 查询失败: {str(e)}",
                "sql": None,
                "result": None,
                "answer": None,
            }

    def query_rag(
        self,
        question: str,
        filters: Optional[dict] = None,
        use_hybrid: bool = True,
    ) -> dict:
        """
        发送到 RAG 服务（video_knowledge collection）

        Returns:
            {
                "answer": str,
                "route_type": "semantic",
                "sources": list
            }
        """
        try:
            payload = {
                "question": question,
                "filters": filters or {},
                "use_hybrid": use_hybrid,
            }
            resp = requests.post(
                f"{self.rag_url}/api/ask_video",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            return {
                "answer": "RAG 服务不可用",
                "route_type": "semantic",
                "sources": [],
                "error": "RAG 服务不可用",
            }
        except Exception as e:
            return {
                "answer": f"RAG 查询失败: {str(e)}",
                "route_type": "semantic",
                "sources": [],
                "error": str(e),
            }

    def check_sql_health(self) -> bool:
        """检查 Text-to-SQL 服务是否可用"""
        try:
            resp = requests.get(f"{self.sql_url}/", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def check_rag_health(self) -> bool:
        """检查 RAG 服务是否可用"""
        try:
            resp = requests.get(f"{self.rag_url}/api/stats", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def get_sql_tables(self) -> list:
        """获取 Text-to-SQL 可用表列表"""
        try:
            resp = requests.get(f"{self.sql_url}/api/tables", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("tables", [])
        except Exception:
            return []

    def get_rag_stats(self) -> dict:
        """获取 RAG 统计信息"""
        try:
            resp = requests.get(f"{self.rag_url}/api/stats", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}
