"""
DuckDB 写入模块
管理视频元数据和 UP 主信息的存储
"""
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import duckdb


class DBWriter:
    """DuckDB 数据写入器"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库连接
        db_path: 数据库文件路径，默认使用环境变量或 ./data/content.db
        """
        if db_path is None:
            db_path = os.getenv('DUCKDB_PATH', './data/content.db')

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = duckdb.connect(str(self.db_path))
        self._init_tables()

    def _init_tables(self):
        """初始化数据表"""
        # video_meta 表：视频元数据
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS video_meta (
                bvid TEXT PRIMARY KEY,
                up_name TEXT NOT NULL,
                up_uid TEXT NOT NULL,
                title TEXT NOT NULL,
                publish_date DATE,
                category TEXT,
                duration INT,
                summary TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # up_info 表：UP 主信息
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS up_info (
                uid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                total_videos INT DEFAULT 0,
                last_update DATE,
                config_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def insert_video(self, video: Dict) -> bool:
        """
        插入或更新单条视频元数据
        video: 包含 bvid, up_name, up_uid, title, publish_date, category, duration 等字段
        """
        try:
            self.conn.execute("""
                INSERT INTO video_meta (bvid, up_name, up_uid, title, publish_date, category, duration, summary, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (bvid) DO UPDATE SET
                    up_name = EXCLUDED.up_name,
                    up_uid = EXCLUDED.up_uid,
                    title = EXCLUDED.title,
                    publish_date = EXCLUDED.publish_date,
                    category = EXCLUDED.category,
                    duration = EXCLUDED.duration,
                    summary = EXCLUDED.summary,
                    tags = EXCLUDED.tags
            """, [
                video.get('bvid'),
                video.get('up_name'),
                video.get('up_uid'),
                video.get('title'),
                video.get('publish_date'),
                video.get('category'),
                video.get('duration'),
                video.get('summary'),
                video.get('tags'),
            ])
            self.conn.commit()
            return True
        except Exception as e:
            print(f"插入视频失败: {e}")
            return False

    def insert_videos(self, videos: List[Dict]) -> int:
        """
        批量插入视频元数据
        返回成功插入的数量
        """
        success_count = 0
        for video in videos:
            if self.insert_video(video):
                success_count += 1
        return success_count

    def update_up_info(self, uid: str, name: str, total_videos: int, config_file: str = None) -> bool:
        """
        更新 UP 主信息
        """
        try:
            self.conn.execute("""
                INSERT INTO up_info (uid, name, total_videos, last_update, config_file)
                VALUES (?, ?, ?, CURRENT_DATE, ?)
                ON CONFLICT (uid) DO UPDATE SET
                    name = EXCLUDED.name,
                    total_videos = EXCLUDED.total_videos,
                    last_update = EXCLUDED.last_update,
                    config_file = EXCLUDED.config_file
            """, [uid, name, total_videos, config_file])
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新 UP 主信息失败: {e}")
            return False

    def get_video_count(self, up_name: str = None) -> int:
        """
        获取视频数量
        up_name: 可选，指定 UP 主名称
        """
        if up_name:
            result = self.conn.execute(
                "SELECT COUNT(*) FROM video_meta WHERE up_name = ?", [up_name]
            ).fetchone()
        else:
            result = self.conn.execute("SELECT COUNT(*) FROM video_meta").fetchone()
        return result[0] if result else 0

    def get_videos(self, up_name: str = None, limit: int = 100) -> List[Dict]:
        """
        获取视频列表
        """
        if up_name:
            cursor = self.conn.execute(
                "SELECT * FROM video_meta WHERE up_name = ? ORDER BY publish_date DESC LIMIT ?",
                [up_name, limit]
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM video_meta ORDER BY publish_date DESC LIMIT ?", [limit]
            )

        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
