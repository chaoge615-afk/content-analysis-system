#!/usr/bin/env python3
"""从 DuckDB 恢复 ChromaDB 数据"""
import os
import sys
from pathlib import Path

# 设置环境变量以连接远程 ChromaDB
os.environ.setdefault("CHROMA_HOST", os.getenv("CHROMA_HOST", "chromadb"))
os.environ.setdefault("CHROMA_PORT", os.getenv("CHROMA_PORT", "8000"))
os.environ.setdefault("SILICONFLOW_API_KEY", os.getenv("SILICONFLOW_API_KEY", ""))
os.environ.setdefault("EMBEDDING_API_KEY", os.getenv("EMBEDDING_API_KEY", os.getenv("SILICONFLOW_API_KEY", "")))

import duckdb
from chroma_writer import ChromaWriter

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/content.db")

def main():
    conn = duckdb.connect(DB_PATH, read_only=True)
    rows = conn.execute("""
        SELECT bvid, up_name, title, category, publish_date, summary, tags, domain
        FROM video_meta
        WHERE summary IS NOT NULL AND summary != ''
    """).fetchall()
    conn.close()

    print(f"从 DuckDB 读取到 {len(rows)} 条摘要记录")

    writer = ChromaWriter(collection_name="video_knowledge")
    count = 0

    for row in rows:
        bvid, up_name, title, category, publish_date, summary, tags, domain = row
        if not summary or not summary.strip():
            continue

        try:
            writer.add_video_with_chunks(
                bvid=bvid,
                up_name=up_name or "",
                title=title or "",
                category=category or "",
                publish_date=str(publish_date) if publish_date else "",
                summary=summary,
                domain=domain or os.getenv("CONTENT_DOMAIN", ""),
            )
            count += 1
            if count % 50 == 0:
                print(f"已写入 {count}/{len(rows)}")
        except Exception as e:
            print(f"写入失败 {bvid}: {e}")

    print(f"恢复完成: {count} 条记录写入 ChromaDB")


if __name__ == "__main__":
    main()