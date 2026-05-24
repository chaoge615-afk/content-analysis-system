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
        db_path: DuckDB 数据库路径，默认使用环境变量 DUCKDB_PATH
        """
        if db_path is None:
            db_path = os.getenv(
                "DUCKDB_PATH",
                str(Path(__file__).parent.parent.parent / "bilibili-monitor" / "data" / "content.db"),
            )
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        """确保 query_log 表存在"""
        try:
            conn = duckdb.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY,
                    question TEXT NOT NULL,
                    route_type TEXT,
                    response_time DECIMAL(8,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.close()
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
            conn = duckdb.connect(self.db_path)
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
            conn.close()
        except Exception as e:
            # 日志记录失败不应影响主流程
            print(f"[QueryLogger] 记录查询日志失败: {e}")

    def get_recent(self, limit: int = 20) -> list:
        """获取最近的查询记录"""
        try:
            conn = duckdb.connect(self.db_path, read_only=True)
            results = conn.execute(
                "SELECT id, question, route_type, response_time, created_at FROM query_log ORDER BY created_at DESC LIMIT ?",
                [limit],
            ).fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"[QueryLogger] 查询日志失败: {e}")
            return []

    def get_stats(self) -> dict:
        """获取查询统计"""
        try:
            conn = duckdb.connect(self.db_path, read_only=True)
            total = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
            by_type = conn.execute(
                "SELECT route_type, COUNT(*) as cnt FROM query_log GROUP BY route_type"
            ).fetchall()
            avg_time = conn.execute(
                "SELECT AVG(response_time) FROM query_log"
            ).fetchone()[0]
            conn.close()
            return {
                "total_queries": total,
                "by_route_type": {row[0]: row[1] for row in by_type if row[0]},
                "avg_response_time": round(avg_time, 2) if avg_time else 0,
            }
        except Exception as e:
            print(f"[QueryLogger] 统计查询失败: {e}")
            return {"total_queries": 0, "by_route_type": {}, "avg_response_time": 0}
