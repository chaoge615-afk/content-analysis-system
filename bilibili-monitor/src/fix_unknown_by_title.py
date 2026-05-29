"""
通过全量视频列表修复 unknown 归属
使用 yt-dlp + Cookie 获取 UP主 的全量视频，标题匹配修复 unknown 记录

支持断点续传：每批标题实时保存到 data/{uid}_videos.json
中断后重新运行自动从上次断点继续

用法:
  python fix_unknown_by_title.py              # 处理全部 4 个 UP主
  python fix_unknown_by_title.py --uid 410110370  # 只处理指定 UP主
  python fix_unknown_by_title.py --match-only      # 跳过获取，只做匹配
"""
import os
import sys
import json
import time
import argparse
import subprocess
import duckdb

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cookies', 'bilibili_cookies.txt')

KNOWN_UPS = {
    "3546912280021515": "恋爱教头桃姐",
    "410110370": "是你的安佳佳呀",
    "3493258856499557": "啊柚的碎碎念",
    "3546767933049757": "夹性学姐在这",
}


def get_db_path():
    return os.getenv("DUCKDB_PATH", "/app/data/content.db")


def clean_title(title):
    remove_chars = '【】！!？?，,。. 、:：；;""\'\'\n\r'
    for c in remove_chars:
        title = title.replace(c, '')
    title = title.replace('　', '').replace(' ', '')
    return title.strip().lower()


def progress_path(uid):
    return os.path.join(DATA_DIR, f'{uid}_videos.json')


def load_progress(uid):
    """加载已有进度"""
    path = progress_path(uid)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('videos', [])
    return []


def save_progress(uid, videos):
    """保存进度到文件"""
    path = progress_path(uid)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'videos': videos}, f, ensure_ascii=False, indent=2)


def yt_dlp_cmd():
    """构建 yt-dlp 基础命令"""
    cmd = ['yt-dlp']
    if os.path.exists(COOKIE_FILE):
        cmd.extend(['--cookies', COOKIE_FILE])
    return cmd


def get_all_bvids(uid, name):
    """第一步：快速获取全部 bvid（flat-playlist，1次请求）"""
    print(f'{name}: 获取视频列表...')
    cmd = yt_dlp_cmd() + [
        '--flat-playlist', '--print', '%(id)s',
        f'https://space.bilibili.com/{uid}/video'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    bvids = [l.strip() for l in result.stdout.strip().split('\n') if l.strip().startswith('BV')]
    print(f'  共 {len(bvids)} 个视频')
    return bvids


def fetch_titles_for_bvids(bvids, existing_map, uid, name):
    """第二步：批量获取标题（50个/批，支持断点续传）"""
    videos = list(existing_map.values()) if existing_map else []
    todo_start = len(videos)  # 已完成的索引位置
    total = len(bvids)
    batch_size = 50

    if todo_start >= total:
        print(f'  所有标题已获取, 跳过')
        return videos

    print(f'  需要获取 {total - todo_start} 个标题 (已有 {todo_start}), 每批 {batch_size} 个')

    for batch_start in range(todo_start, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        print(f'  批次 [{batch_start+1}-{batch_end}/{total}] 获取中...', end=' ', flush=True)

        cmd = yt_dlp_cmd() + [
            '--playlist-start', str(batch_start + 1),
            '--playlist-end', str(batch_end),
            '--print', '%(id)s||%(title)s',
            '--sleep-interval', '1',
            '--max-sleep-interval', '3',
            f'https://space.bilibili.com/{uid}/video'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            lines = result.stdout.strip().split('\n')
            new_count = 0
            for line in lines:
                line = line.strip()
                if '||' in line and line.startswith('BV'):
                    parts = line.split('||', 1)
                    bvid, title = parts[0], parts[1] if len(parts) > 1 else ''
                    if title and title != 'NA' and bvid not in existing_map:
                        v = {'bvid': bvid, 'title': title, 'title_clean': clean_title(title)}
                        videos.append(v)
                        existing_map[bvid] = v
                        new_count += 1

            save_progress(uid, videos)
            print(f'{new_count} 个, 累计 {len(videos)}')

        except Exception as e:
            print(f'失败: {e}')
            save_progress(uid, videos)
            print(f'  已保存 {len(videos)} 个, 可稍后继续')

        # 批次间休息 3 秒
        if batch_end < total:
            time.sleep(3)

    print(f'  {name}: 完成, 共 {len(videos)} 个视频\n')
    return videos


def fetch_videos(uid, name):
    """获取 UP主 的全量视频列表（yt-dlp + Cookie）"""
    # 加载已有进度
    existing_videos = load_progress(uid)
    existing_map = {v['bvid']: v for v in existing_videos}
    print(f'{name} (uid={uid}): 已有 {len(existing_videos)} 个视频\n')

    # 步骤1: 快速获取全部 bvid
    bvids = get_all_bvids(uid, name)

    # 步骤2: 逐视频获取标题（断点续传）
    videos = fetch_titles_for_bvids(bvids, existing_map, uid, name)

    return videos


def match_and_fix(title_map):
    """用标题映射表匹配并修复 unknown 记录"""
    print('=== 步骤 2: 匹配 unknown 记录 ===\n')

    conn = duckdb.connect(get_db_path())

    unknown_rows = conn.execute("""
        SELECT bvid, title, created_at
        FROM video_meta
        WHERE up_name = 'unknown' AND bvid NOT LIKE 'BV%'
    """).fetchall()

    print(f'找到 {len(unknown_rows)} 个 unknown 记录\n')

    matched = 0
    unmatched = 0
    matched_by_up = {name: 0 for name in KNOWN_UPS.values()}

    for fake_bvid, title, created_at in unknown_rows:
        title_clean = clean_title(title)

        if title_clean in title_map:
            real_bvid, uid, up_name = title_map[title_clean]

            # 检查真实 bvid 是否已存在于数据库中
            existing = conn.execute(
                "SELECT COUNT(*) FROM video_meta WHERE bvid = ?", [real_bvid]
            ).fetchone()[0]

            if existing > 0:
                # 真实记录已存在，删除 unknown 重复记录
                conn.execute(
                    "DELETE FROM video_meta WHERE bvid = ? AND up_name = 'unknown'",
                    [fake_bvid]
                )
            else:
                conn.execute("""
                    UPDATE video_meta
                    SET up_name = ?, up_uid = ?, bvid = ?
                    WHERE bvid = ? AND up_name = 'unknown'
                """, [up_name, uid, real_bvid, fake_bvid])

            matched += 1
            matched_by_up[up_name] += 1
            if matched <= 20 or matched % 50 == 0:
                print(f'[{matched}] {title[:50]} → {up_name}')
        else:
            unmatched += 1

    conn.commit()
    conn.close()

    print(f'\n=== 统计 ===')
    print(f'匹配成功: {matched}')
    print(f'匹配失败: {unmatched}')
    print(f'\n各 UP主 匹配数:')
    for name, count in matched_by_up.items():
        print(f'  {name}: {count}')

    return matched, unmatched


def main():
    parser = argparse.ArgumentParser(description='通过标题匹配修复 unknown 视频归属')
    parser.add_argument('--uid', help='只处理指定 UP主 (默认全部)')
    parser.add_argument('--match-only', action='store_true', help='跳过获取, 只从已有进度文件做匹配')
    args = parser.parse_args()

    if args.uid and args.uid not in KNOWN_UPS:
        print(f'未知 UID: {args.uid}')
        print(f'已知 UID: {", ".join(KNOWN_UPS.keys())}')
        sys.exit(1)

    uids_to_fetch = [args.uid] if args.uid else list(KNOWN_UPS.keys())

    if not args.match_only:
        print(f'=== 步骤 1: 获取 {len(uids_to_fetch)} 个 UP主 的视频列表 ===\n')
        cookie_status = "存在" if os.path.exists(COOKIE_FILE) else "不存在"
        print(f'Cookie 文件: {COOKIE_FILE} ({cookie_status})\n')

        for uid in uids_to_fetch:
            name = KNOWN_UPS[uid]
            fetch_videos(uid, name)

    # 构建标题映射表（从所有进度文件加载）
    print('\n=== 构建标题映射表 ===')
    title_map = {}

    for uid, name in KNOWN_UPS.items():
        videos = load_progress(uid)
        for v in videos:
            title_map[v['title_clean']] = (v['bvid'], uid, name)
        print(f'  {name}: {len(videos)} 个视频')

    print(f'\n映射表总计: {len(title_map)} 个标题\n')

    match_and_fix(title_map)

    # 统计更新后状态
    conn = duckdb.connect(get_db_path(), read_only=True)
    remaining = conn.execute("SELECT COUNT(*) FROM video_meta WHERE up_name = 'unknown'").fetchone()[0]
    print(f'\nunknown 剩余: {remaining}')

    print(f'\n各 UP主 当前视频数:')
    for uid, name in KNOWN_UPS.items():
        count = conn.execute("SELECT COUNT(*) FROM video_meta WHERE up_uid = ?", [uid]).fetchone()[0]
        print(f'  {name}: {count}')
    conn.close()

    print('\n完成!')


if __name__ == '__main__':
    main()