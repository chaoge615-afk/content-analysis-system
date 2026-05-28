"""
历史数据迁移脚本 - Phase 1.8
扫描原始转写 txt 文件，提取 BVID，补全元数据，精炼并入库

数据源: E:/情感素材库/ 下的原始 txt 文件
文件命名: 标题 [BVxxx].txt
流程: 提取BVID → 调B站API补全元数据 → 精炼 → 写入DuckDB + ChromaDB
"""
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

# 添加 scripts 目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# 添加 shared/ 目录（加载 shared_config, shared_embeddings）
_SHARED_DIR = SCRIPT_DIR.parent.parent / "shared"
sys.path.insert(0, str(_SHARED_DIR))

from db_writer import DBWriter
from chroma_writer import ChromaWriter
from refiner import refine_and_classify
from bili_api import get_video_info_by_bvid


# ─── 文件名解析 ─────────────────────────────────────────────────

def extract_bvid_from_filename(filename: str) -> Optional[str]:
    """从文件名提取 BVID"""
    m = re.search(r'\[(BV[a-zA-Z0-9]+)\]', filename)
    return m.group(1) if m else None


def extract_title_from_filename(filename: str) -> str:
    """从文件名提取标题（去掉 [BVxxx].txt）"""
    title = re.sub(r'\s*\[BV[a-zA-Z0-9]+\]\.txt$', '', filename)
    return title.strip()


def extract_up_name_from_path(filepath: Path, source_dir: Path) -> Optional[str]:
    """
    从文件路径提取 UP 主名称
    如果文件在子目录中（如 E:/情感素材库/啊柚的碎碎念/xxx.txt），
    子目录名就是 UP 主名称
    """
    try:
        rel_path = filepath.relative_to(source_dir)
        parts = rel_path.parts
        # 如果在子目录中，第一个 part 就是 UP 主名
        if len(parts) > 1:
            return parts[0]
    except:
        pass
    return None


# ─── 主迁移逻辑 ─────────────────────────────────────────────────

def migrate_history(
    source_dir: str = "E:/情感素材库",
    skip_refine: bool = False,
    dry_run: bool = False,
    delay: float = 1.0,
):
    """
    迁移历史原始 txt 文件

    source_dir: 原始 txt 文件所在目录
    skip_refine: 跳过精炼（只入库原始文本）
    dry_run: 只扫描不写入
    delay: B站 API 请求间隔（秒），避免被限流
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"错误: 源目录不存在: {source_dir}")
        return

    # 扫描 txt 文件（递归扫描子目录）
    txt_files = sorted(source_path.rglob("*.txt"))
    if not txt_files:
        print(f"错误: 未找到 txt 文件: {source_dir}")
        return

    print(f"{'='*60}")
    print(f"历史数据迁移: {source_dir}")
    print(f"文件数: {len(txt_files)}")
    print(f"模式: {'DRY RUN' if dry_run else '正式迁移'}")
    print(f"精炼: {'跳过' if skip_refine else '启用'}")
    print(f"{'='*60}\n")

    # 统计
    stats = {
        'total': len(txt_files),
        'has_bvid': 0,
        'no_bvid': 0,
        'api_ok': 0,
        'api_fail': 0,
        'refined': 0,
        'db_ok': 0,
        'chroma_ok': 0,
        'skipped': 0,
    }

    if dry_run:
        # DRY RUN 模式：只统计
        for txt_file in txt_files:
            bvid = extract_bvid_from_filename(txt_file.name)
            if bvid:
                stats['has_bvid'] += 1
            else:
                stats['no_bvid'] += 1

        print(f"\n扫描结果:")
        print(f"  有 BVID: {stats['has_bvid']}")
        print(f"  无 BVID: {stats['no_bvid']}")
        return stats

    # 初始化写入器
    db = DBWriter()
    chroma = ChromaWriter()

    for i, txt_file in enumerate(txt_files, 1):
        print(f"\n[{i}/{len(txt_files)}] {txt_file.name[:60]}...")

        # 提取 BVID
        bvid = extract_bvid_from_filename(txt_file.name)
        title_from_file = extract_title_from_filename(txt_file.name)

        if not bvid:
            print(f"  ⚠️ 无 BVID，跳过")
            stats['no_bvid'] += 1
            stats['skipped'] += 1
            continue

        stats['has_bvid'] += 1

        # 读取文本内容
        full_text = txt_file.read_text(encoding='utf-8').strip()
        if len(full_text) < 30:
            print(f"  ⚠️ 内容太短（{len(full_text)}字），跳过")
            stats['skipped'] += 1
            continue

        # 调 B站 API 补全元数据
        print(f"  BVID: {bvid}，获取元数据...")
        video_info = get_video_info_by_bvid(bvid)
        time.sleep(delay)

        if video_info:
            stats['api_ok'] += 1
            title = video_info['title']
            up_name = video_info['owner_name']
            up_uid = video_info['owner_mid']
            pub_date = video_info['publish_date']
            category = video_info['category']
            duration = video_info['duration']
            print(f"  ✅ UP主: {up_name}, 标题: {title[:40]}")
        else:
            stats['api_fail'] += 1
            # API 失败时使用文件名中的信息
            title = title_from_file
            # 尝试从目录结构提取 UP 主名称
            up_name = extract_up_name_from_path(txt_file, source_path) or "unknown"
            up_uid = "unknown"
            pub_date = None
            category = ""
            duration = 0
            print(f"  ⚠️ 使用文件名信息: {title[:40]}, UP主: {up_name}")

        # 精炼
        summary = None
        auto_category = ""
        if not skip_refine and len(full_text) > 100:
            print(f"  精炼中...")
            try:
                summary, auto_category = refine_and_classify(full_text)
                if summary:
                    stats['refined'] += 1
                    print(f"  ✅ 精炼完成")
                    if not category and auto_category:
                        category = auto_category
                else:
                    print(f"  ⚠️ 精炼失败")
            except Exception as e:
                print(f"  ⚠️ 精炼异常: {e}")

        # 写入 DuckDB
        video_record = {
            'bvid': bvid,
            'up_name': up_name,
            'up_uid': up_uid,
            'title': title,
            'publish_date': pub_date,
            'category': category,
            'duration': duration,
            'summary': summary,
            'tags': '',
        }
        if db.insert_video(video_record):
            stats['db_ok'] += 1
            print(f"  ✅ DuckDB 写入成功")
        else:
            print(f"  ❌ DuckDB 写入失败")

        # 写入 ChromaDB
        chroma_count = chroma.add_video_with_chunks(
            bvid=bvid,
            up_name=up_name,
            title=title,
            category=category,
            publish_date=str(pub_date) if pub_date else '',
            full_text=full_text,
            summary=summary,
        )
        if chroma_count > 0:
            stats['chroma_ok'] += 1
            print(f"  ✅ ChromaDB 写入成功（{chroma_count} 个文档）")
        else:
            print(f"  ❌ ChromaDB 写入失败")

    db.close()

    # 打印统计
    print(f"\n{'='*60}")
    print(f"迁移完成:")
    print(f"  总文件: {stats['total']}")
    print(f"  有 BVID: {stats['has_bvid']}")
    print(f"  无 BVID: {stats['no_bvid']}")
    print(f"  API 成功: {stats['api_ok']}")
    print(f"  API 失败: {stats['api_fail']}")
    print(f"  精炼成功: {stats['refined']}")
    print(f"  DuckDB: {stats['db_ok']}")
    print(f"  ChromaDB: {stats['chroma_ok']}")
    print(f"  跳过: {stats['skipped']}")
    print(f"{'='*60}")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="迁移历史原始 txt 文件")
    parser.add_argument("--source", default="E:/情感素材库", help="原始 txt 目录")
    parser.add_argument("--skip-refine", action="store_true", help="跳过精炼")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不写入")
    parser.add_argument("--delay", type=float, default=1.0, help="API 请求间隔（秒）")
    args = parser.parse_args()

    migrate_history(
        source_dir=args.source,
        skip_refine=args.skip_refine,
        dry_run=args.dry_run,
        delay=args.delay,
    )
