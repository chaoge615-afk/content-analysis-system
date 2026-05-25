"""
查询日志模块
将每次查询记录到 DuckDB query_log 表，用于分析和统计
"""

import os
import duckdb
from pathlib import Path
from typing import Optional
from datetime import datetime


class QueryLogger:
    """查询日志记录器"""

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化日志记录器
        db_path: DuckDB 数据库路径，默认使用独立的 query_log.db（避免与 content.db 锁冲突）
        """
        if db_path is None:
            # 使用独立的数据库文件，避免与 text-to-sql 锁冲突
            data_dir = os.getenv(
                "DATA_DIR",
                str(Path(__file__).parent.parent.parent / "bilibili-monitor" / "data"),
            )
            db_path = os.path.join(data_dir, "query_log.db")
        self.db_path = db_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._ensure_table()

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """获取 DuckDB 连接（query_log.db 仅被 router-agent 访问，可安全复用）"""
        if self._conn is None:
            # 确保数据目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._conn = duckdb.connect(self.db_path)
        return self._conn

    def _ensure_table(self):
        """确保 query_log 表存在"""
        try:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY,
                    question TEXT NOT NULL,
                    route_type TEXT,
                    response_time DECIMAL(8,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception as e:
            print(f"[QueryLogger] 初始化 query_log 表失败: {e}")

    def log(
        self,
        question: str,
        route_type: str,
        response_time: float,
    ):
        """
        记录一条查询日志

        Args:
            question: 用户问题
            route_type: 路由类型 (structured/semantic/hybrid)
            response_time: 响应时间（秒）
        """
        try:
            conn = self._get_conn()
            # 获取下一个 ID
            max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM query_log").fetchone()[0]
            next_id = max_id + 1

            conn.execute(
                """
                INSERT INTO query_log (id, question, route_type, response_time, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [next_id, question[:500], route_type, round(response_time, 2), datetime.now()],
            )
        except Exception as e:
            # 日志记录失败不应影响主流程
            print(f"[QueryLogger] 记录查询日志失败: {e}")

    def get_recent(self, limit: int = 20) -> list:
        """获取最近的查询记录"""
        try:
            conn = self._get_conn()
            results = conn.execute(
                "SELECT id, question, route_type, response_time, created_at FROM query_log ORDER BY created_at DESC LIMIT ?",
                [limit],
            ).fetchall()
            return results
        except Exception as e:
            print(f"[QueryLogger] 查询日志失败: {e}")
            return []

    def get_paginated(
        self, page: int = 1, page_size: int = 20, route_type: Optional[str] = None
    ) -> dict:
        """
        分页查询日志

        Args:
            page: 页码（从 1 开始）
            page_size: 每页条数
            route_type: 按路由类型过滤（可选）

        Returns:
            { items, total, page, page_size, total_pages }
        """
        try:
            conn = self._get_conn()

            # 构建 WHERE 条件
            where = ""
            params = []
            if route_type:
                where = "WHERE route_type = ?"
                params.append(route_type)

            # 总数
            total = conn.execute(
                f"SELECT COUNT(*) FROM query_log {where}", params
            ).fetchone()[0]

            total_pages = max(1, (total + page_size - 1) // page_size)
            offset = (page - 1) * page_size

            # 分页数据
            results = conn.execute(
                f"""SELECT id, question, route_type, response_time, created_at
                    FROM query_log {where}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            ).fetchall()

            items = [
                {
                    "id": r[0],
                    "question": r[1],
                    "route_type": r[2],
                    "response_time": float(r[3]) if r[3] else 0,
                    "created_at": str(r[4]),
                }
                for r in results
            ]

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
        except Exception as e:
            print(f"[QueryLogger] 分页查询失败: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    def get_stats(self) -> dict:
        """获取查询统计"""
        try:
            conn = self._get_conn()
            total = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
            by_type = conn.execute(
                "SELECT route_type, COUNT(*) as cnt FROM query_log GROUP BY route_type"
            ).fetchall()
            avg_time = conn.execute(
                "SELECT AVG(response_time) FROM query_log"
            ).fetchone()[0]
            return {
                "total_queries": total,
                "by_route_type": {row[0]: row[1] for row in by_type if row[0]},
                "avg_response_time": round(avg_time, 2) if avg_time else 0,
            }
        except Exception as e:
            print(f"[QueryLogger] 统计查询失败: {e}")
            return {"total_queries": 0, "by_route_type": {}, "avg_response_time": 0}
