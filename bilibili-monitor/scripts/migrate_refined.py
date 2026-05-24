"""
精炼数据迁移脚本 - Phase 1.9
扫描 relationship-analysis 已有的精炼 txt 文件，补全元数据并入库

数据源: relationship-analysis/references/情感素材库/ 下的精炼 txt 文件
文件结构: 分类目录/标题.txt（约17%有 BVID）
流程: 提取BVID → 调B站API补全元数据 → 写入DuckDB + ChromaDB
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

# 添加根目录（加载 shared_config）
ROOT_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from db_writer import DBWriter
from chroma_writer import ChromaWriter
from bili_api import get_video_info_by_bvid


# ─── 文件名解析 ─────────────────────────────────────────────────

def extract_bvid_from_filename(filename: str) -> Optional[str]:
    """从文件名提取 BVID"""
    m = re.search(r'\[(BV[a-zA-Z0-9]+)\]', filename)
    if m:
        return m.group(1)
    # 也尝试匹配 BVxxx 格式（不带方括号）
    m = re.search(r'(BV[a-zA-Z0-9]{10})', filename)
    return m.group(1) if m else None


def extract_category_from_path(filepath: Path) -> str:
    """从文件路径提取分类目录名"""
    return filepath.parent.name


# ─── 主迁移逻辑 ─────────────────────────────────────────────────

def migrate_refined(
    source_dir: str = None,
    dry_run: bool = False,
    delay: float = 0.5,
    with_bvid_only: bool = False,
):
    """
    迁移精炼 txt 文件

    source_dir: 精炼文件根目录（默认: relationship-analysis/references/情感素材库）
    dry_run: 只扫描不写入
    delay: B站 API 请求间隔（秒）
    with_bvid_only: 只处理有 BVID 的文件
    """
    if source_dir is None:
        source_dir = str(ROOT_DIR / "relationship-analysis" / "references" / "情感素材库")

    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"错误: 源目录不存在: {source_dir}")
        return

    # 递归扫描所有分类子目录下的 txt 文件
    txt_files = sorted(source_path.rglob("*.txt"))
    if not txt_files:
        print(f"错误: 未找到 txt 文件: {source_dir}")
        return

    print(f"{'='*60}")
    print(f"精炼数据迁移: {source_dir}")
    print(f"文件数: {len(txt_files)}")
    print(f"模式: {'DRY RUN' if dry_run else '正式迁移'}")
    print(f"范围: {'仅 BVID' if with_bvid_only else '全部'}")
    print(f"{'='*60}\n")

    # 统计
    stats = {
        'total': len(txt_files),
        'has_bvid': 0,
        'no_bvid': 0,
        'api_ok': 0,
        'api_fail': 0,
        'db_ok': 0,
        'chroma_ok': 0,
        'skipped': 0,
        'categories': {},
    }

    # 预扫描：统计 BVID 分布和分类分布
    for txt_file in txt_files:
        bvid = extract_bvid_from_filename(txt_file.name)
        category = extract_category_from_path(txt_file)

        stats['categories'][category] = stats['categories'].get(category, 0) + 1

        if bvid:
            stats['has_bvid'] += 1
        else:
            stats['no_bvid'] += 1

    print(f"扫描结果:")
    print(f"  有 BVID: {stats['has_bvid']} ({stats['has_bvid']*100//stats['total']}%)")
    print(f"  无 BVID: {stats['no_bvid']} ({stats['no_bvid']*100//stats['total']}%)")
    print(f"  分类数: {len(stats['categories'])}")
    print()

    if dry_run:
        print(f"分类分布:")
        for cat, count in sorted(stats['categories'].items()):
            print(f"  {cat}: {count}")
        return stats

    if with_bvid_only:
        txt_files = [f for f in txt_files if extract_bvid_from_filename(f.name)]
        print(f"仅处理有 BVID 的文件: {len(txt_files)} 个\n")

    # 初始化写入器
    db = DBWriter()
    chroma = ChromaWriter()

    for i, txt_file in enumerate(txt_files, 1):
        bvid = extract_bvid_from_filename(txt_file.name)
        category = extract_category_from_path(txt_file)
        title = txt_file.stem  # 文件名即标题

        # 进度显示（每 50 个或首尾显示）
        if i <= 3 or i % 50 == 0 or i == len(txt_files):
            print(f"\n[{i}/{len(txt_files)}] {category}/{title[:40]}...")

        # 读取精炼内容
        refined_text = txt_file.read_text(encoding='utf-8').strip()
        if len(refined_text) < 30:
            stats['skipped'] += 1
            continue

        # 确定元数据
        up_name = "unknown"
        up_uid = "unknown"
        pub_date = None
        duration = 0
        api_title = title

        if bvid:
            # 有 BVID：调 API 补全
            print(f"  BVID: {bvid}，获取元数据...")
            video_info = get_video_info_by_bvid(bvid)
            time.sleep(delay)

            if video_info:
                stats['api_ok'] += 1
                api_title = video_info['title']
                up_name = video_info['owner_name']
                up_uid = video_info['owner_mid']
                pub_date = video_info['publish_date']
                duration = video_info['duration']
                print(f"  ✅ UP主: {up_name}")
            else:
                stats['api_fail'] += 1
                print(f"  ⚠️ API 失败，使用文件名")
        else:
            # 无 BVID：使用文件名信息
            bvid = f"unknown_{txt_file.stem[:20].replace(' ', '_')}"

        # 写入 DuckDB
        video_record = {
            'bvid': bvid,
            'up_name': up_name,
            'up_uid': up_uid,
            'title': api_title,
            'publish_date': pub_date,
            'category': category,  # 使用情感分类目录名
            'duration': duration,
            'summary': refined_text,  # 精炼内容作为 summary
            'tags': '',
        }
        if db.insert_video(video_record):
            stats['db_ok'] += 1
        else:
            pass  # 静默失败，避免刷屏

        # 写入 ChromaDB（精炼内容作为 summary，无全文）
        chroma_count = chroma.add_video_with_chunks(
            bvid=bvid,
            up_name=up_name,
            title=api_title,
            category=category,
            publish_date=str(pub_date) if pub_date else '',
            full_text=None,
            summary=refined_text,
        )
        if chroma_count > 0:
            stats['chroma_ok'] += 1

        # 每 100 个打印一次进度
        if i % 100 == 0:
            print(f"\n  --- 进度: {i}/{len(txt_files)} | DuckDB: {stats['db_ok']} | ChromaDB: {stats['chroma_ok']} ---")

    db.close()

    # 打印统计
    print(f"\n{'='*60}")
    print(f"迁移完成:")
    print(f"  总文件: {stats['total']}")
    print(f"  有 BVID: {stats['has_bvid']}")
    print(f"  无 BVID: {stats['no_bvid']}")
    print(f"  API 成功: {stats['api_ok']}")
    print(f"  API 失败: {stats['api_fail']}")
    print(f"  DuckDB: {stats['db_ok']}")
    print(f"  ChromaDB: {stats['chroma_ok']}")
    print(f"  跳过: {stats['skipped']}")
    print(f"{'='*60}")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="迁移精炼 txt 文件")
    parser.add_argument("--source", default=None, help="精炼文件根目录")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不写入")
    parser.add_argument("--delay", type=float, default=0.5, help="API 请求间隔（秒）")
    parser.add_argument("--with-bvid-only", action="store_true", help="只处理有 BVID 的文件")
    args = parser.parse_args()

    migrate_refined(
        source_dir=args.source,
        dry_run=args.dry_run,
        delay=args.delay,
        with_bvid_only=args.with_bvid_only,
    )
