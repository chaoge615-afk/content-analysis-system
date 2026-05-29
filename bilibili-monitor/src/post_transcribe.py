"""
转写后处理：精炼 + DuckDB 入库 + ChromaDB 入库
可被 monitor.py 调用，也可独立运行
"""
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from db_writer import DBWriter
from chroma_writer import ChromaWriter
from refiner import refine_and_classify


def extract_bvid_from_filename(filename: str) -> Optional[str]:
    """从文件名提取 BVID"""
    m = re.search(r'\[(BV[a-zA-Z0-9]+)\]', filename)
    return m.group(1) if m else None


def extract_title_from_filename(filename: str) -> str:
    """从文件名提取标题"""
    # 去掉 [BVxxx].txt 部分
    title = re.sub(r'\s*\[BV[a-zA-Z0-9]+\]\.txt$', '', filename)
    return title.strip()


def process_transcripts(
    transcript_dir: str,
    up_name: str,
    up_uid: str,
    videos_info: Dict[str, Dict] = None,
    skip_refine: bool = False,
) -> Dict:
    """
    处理转写后的 txt 文件：精炼 + 入库

    transcript_dir: txt 文件所在目录
    up_name: UP 主名称
    up_uid: UP 主 UID
    videos_info: 视频元数据字典 {bvid: {title, publish_date, category, duration, ...}}
    skip_refine: 跳过精炼（只入库不精炼）

    返回: 处理结果统计
    """
    transcript_path = Path(transcript_dir)
    txt_files = sorted(transcript_path.glob("*.txt"))

    if not txt_files:
        print("没有找到 txt 文件")
        return {"total": 0, "refined": 0, "db_ok": 0, "chroma_ok": 0}

    print(f"\n处理 {len(txt_files)} 个转写文件...")
    videos_info = videos_info or {}

    stats = {"total": len(txt_files), "refined": 0, "db_ok": 0, "chroma_ok": 0}

    db = DBWriter()
    chroma = ChromaWriter()

    for i, txt_file in enumerate(txt_files, 1):
        bvid = extract_bvid_from_filename(txt_file.name)
        title = extract_title_from_filename(txt_file.name)

        print(f"\n[{i}/{len(txt_files)}] {title[:50]}...")

        # 读取转写文本
        full_text = txt_file.read_text(encoding='utf-8').strip()
        if len(full_text) < 30:
            print(f"  ⚠️ 内容太短（{len(full_text)}字），跳过")
            continue

        # 获取视频元数据
        info = videos_info.get(bvid, {})
        pub_date = info.get('publish_date', '')
        category = info.get('category', '')
        duration = info.get('duration', 0)

        # 精炼（带外层重试机制，覆盖 429 限流场景）
        summary = None
        auto_category = ""
        if not skip_refine and len(full_text) > 100:
            print(f"  精炼中...")
            for refine_attempt in range(3):
                try:
                    summary, auto_category = refine_and_classify(full_text)
                    if summary:
                        stats["refined"] += 1
                        print(f"  ✅ 精炼完成")
                        if not category:
                            category = auto_category
                        break
                    else:
                        if refine_attempt < 2:
                            wait = 60 * (refine_attempt + 1)
                            print(f"  ⚠️ 精炼失败，{wait}s 后重试 ({refine_attempt+1}/3)")
                            time.sleep(wait)
                except Exception as e:
                    print(f"  ⚠️ 精炼异常: {e}")
                    if refine_attempt < 2:
                        wait = 60 * (refine_attempt + 1)
                        print(f"  {wait}s 后重试 ({refine_attempt+1}/3)")
                        time.sleep(wait)
            if not summary:
                print(f"  ⚠️ 精炼最终失败，使用原文")

        # 写入 DuckDB
        video_record = {
            'bvid': bvid or f"unknown_{txt_file.stem}",
            'up_name': up_name,
            'up_uid': up_uid,
            'title': title,
            'publish_date': pub_date or None,
            'category': category,
            'duration': duration,
            'summary': summary,
            'tags': '',
        }
        if db.insert_video(video_record):
            stats["db_ok"] += 1
            print(f"  ✅ DuckDB 写入成功")
        else:
            print(f"  ❌ DuckDB 写入失败")

        # 写入 ChromaDB
        chroma_count = chroma.add_video_with_chunks(
            bvid=bvid or f"unknown_{txt_file.stem}",
            up_name=up_name,
            title=title,
            category=category,
            publish_date=str(pub_date) if pub_date else '',
            full_text=full_text,
            summary=summary,
        )
        if chroma_count > 0:
            stats["chroma_ok"] += 1
            print(f"  ✅ ChromaDB 写入成功（{chroma_count} 个文档）")
        else:
            print(f"  ❌ ChromaDB 写入失败")

    db.close()

    print(f"\n{'='*50}")
    print(f"处理完成: {stats['db_ok']}/{stats['total']} DuckDB, "
          f"{stats['chroma_ok']}/{stats['total']} ChromaDB, "
          f"{stats['refined']} 精炼成功")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="转写后处理：精炼 + 入库")
    parser.add_argument("transcript_dir", help="转写 txt 文件所在目录")
    parser.add_argument("--up-name", required=True, help="UP主名称")
    parser.add_argument("--up-uid", required=True, help="UP主UID")
    parser.add_argument("--skip-refine", action="store_true", help="跳过精炼，直接入库")
    args = parser.parse_args()

    process_transcripts(
        transcript_dir=args.transcript_dir,
        up_name=args.up_name,
        up_uid=args.up_uid,
        skip_refine=args.skip_refine,
    )
