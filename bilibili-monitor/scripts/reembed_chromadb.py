"""
ChromaDB 重新嵌入脚本
将 DuckDB 中的数据用 SiliconFlow embeddings 重新写入 ChromaDB

原因：迁移时使用了本地 ONNX 模型（384维），
但项目标准是 SiliconFlow BAAI/bge-large-zh-v1.5（1024维），
需要重新嵌入以保证语义搜索一致性。
"""
import os
import sys
import time
from pathlib import Path

# 添加路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from db_writer import DBWriter
from chroma_writer import ChromaWriter


def reembed_chromadb(
    dry_run: bool = False,
    batch_delay: float = 0.5,
):
    """
    从 DuckDB 读取元数据和摘要，用 SiliconFlow embeddings 重写 ChromaDB
    """
    # 读取 DuckDB 所有记录
    db = DBWriter()
    total = db.get_video_count()
    print(f"{'='*60}")
    print(f"ChromaDB 重新嵌入")
    print(f"DuckDB 记录数: {total}")
    print(f"模式: {'DRY RUN' if dry_run else '正式执行'}")
    print(f"Embedding: SiliconFlow BAAI/bge-large-zh-v1.5 (1024维)")
    print(f"{'='*60}\n")

    # 获取所有视频记录
    rows = db.conn.execute('''
        SELECT bvid, up_name, title, category,
               COALESCE(publish_date::VARCHAR, '') as publish_date,
               summary
        FROM video_meta
        ORDER BY created_at
    ''').fetchall()
    db.close()

    print(f"读取到 {len(rows)} 条记录\n")

    if dry_run:
        with_summary = sum(1 for r in rows if r[5])
        print(f"  有摘要: {with_summary}")
        print(f"  无摘要: {len(rows) - with_summary}")
        return

    # 初始化 ChromaWriter（使用 SiliconFlow embeddings）
    chroma = ChromaWriter()

    # 清空现有 collection（384维旧数据）
    print("清空旧 collection（384维 ONNX 数据）...")
    chroma.client.delete_collection("video_knowledge")
    chroma.collection = chroma.client.get_or_create_collection(
        name="video_knowledge",
        metadata={"description": "B站视频转写和精炼知识库"},
    )
    print("✅ 已清空\n")

    # 准备批量写入
    stats = {'total': len(rows), 'success': 0, 'fail': 0, 'docs': 0}

    # 单条写入，避免 413 错误
    max_text_len = 2000  # 截断到 2000 字符

    for i, (bvid, up_name, title, category, pub_date, summary) in enumerate(rows, 1):
        if i % 100 == 0 or i == len(rows):
            print(f"  进度: {i}/{len(rows)} | 文档数: {stats['docs']} | 失败: {stats['fail']}")

        # 添加摘要文档
        if summary and summary.strip():
            summary_text = summary[:max_text_len]
            doc_id = f"{bvid}_summary_0"
            try:
                chroma.add_documents(
                    ids=[doc_id],
                    documents=[summary_text],
                    metadatas=[{
                        "bvid": bvid,
                        "up_name": up_name or "",
                        "title": title or "",
                        "category": category or "",
                        "publish_date": pub_date or "",
                        "content_type": "summary",
                        "source": "bilibili",
                    }],
                )
                stats['docs'] += 1
                stats['success'] += 1
            except Exception as e:
                if "413" in str(e):
                    # 进一步截断
                    try:
                        chroma.add_documents(
                            ids=[doc_id],
                            documents=[summary_text[:500]],
                            metadatas=[{
                                "bvid": bvid,
                                "up_name": up_name or "",
                                "title": title or "",
                                "category": category or "",
                                "publish_date": pub_date or "",
                                "content_type": "summary",
                                "source": "bilibili",
                            }],
                        )
                        stats['docs'] += 1
                        stats['success'] += 1
                    except Exception:
                        stats['fail'] += 1
                else:
                    stats['fail'] += 1

            time.sleep(batch_delay)

    # 统计
    final_count = chroma.collection.count()
    print(f"\n{'='*60}")
    print(f"重新嵌入完成:")
    print(f"  DuckDB 记录: {stats['total']}")
    print(f"  批量写入成功: {stats['success']}")
    print(f"  批量写入失败: {stats['fail']}")
    print(f"  ChromaDB 文档数: {final_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ChromaDB 重新嵌入（SiliconFlow）")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入")
    parser.add_argument("--batch-delay", type=float, default=0.1, help="请求间隔（秒）")
    args = parser.parse_args()

    reembed_chromadb(
        dry_run=args.dry_run,
        batch_delay=args.batch_delay,
    )
