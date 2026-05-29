"""
通过全量视频列表修复 unknown 归属
从 B站 API 获取 UP主 的全量视频，用标题匹配修复 unknown 记录

支持断点续传：每页结果实时保存到 data/{uid}_videos.json
中断后重新运行自动从上次断点继续

用法:
  python fix_unknown_by_title.py              # 处理全部 4 个 UP主
  python fix_unknown_by_title.py --uid 3546912280021515  # 只处理指定 UP主
  python fix_unknown_by_title.py --match-only            # 跳过 API 获取，只做匹配
"""
import os
import sys
import json
import time
import argparse
import duckdb
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')


def get_db_path():
    return os.getenv("DUCKDB_PATH", "/app/data/content.db")

KNOWN_UPS = {
    "3546912280021515": "恋爱教头桃姐",
    "410110370": "是你的安佳佳呀",
    "3493258856499557": "啊柚的碎碎念",
    "3546767933049757": "夹性学姐在这",
}


def clean_title(title):
    remove_chars = '【】！!？?，,。. 、:：；;""\'\'\n\r'
    for c in remove_chars:
        title = title.replace(c, '')
    title = title.replace('　', '').replace(' ', '')
    return title.strip().lower()


def progress_path(uid):
    return os.path.join(DATA_DIR, f'{uid}_videos.json')


def load_progress(uid):
    """加载已有进度，返回 (videos_list, last_page)"""
    path = progress_path(uid)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('videos', []), data.get('last_page', 0)
    return [], 0


def save_progress(uid, videos, last_page):
    """保存进度到文件"""
    path = progress_path(uid)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'videos': videos, 'last_page': last_page}, f, ensure_ascii=False, indent=2)


def fetch_videos(uid, name, start_page=1):
    """获取 UP主 的全量视频列表（支持断点续传）"""
    videos, _ = load_progress(uid)
    existing_bvids = {v['bvid'] for v in videos}
    page = start_page
    api_count = 0
    retry_count = 0
    max_retries = 5

    print(f'{name} (uid={uid}): 已有 {len(videos)} 个视频, 从第 {start_page} 页继续\n')

    while True:
        try:
            resp = requests.get(
                'https://api.bilibili.com/x/space/arc/search',
                params={
                    'mid': uid,
                    'ps': 30,
                    'pn': page,
                    'order': 'pubdate'
                },
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                timeout=10
            )
            api_count += 1

            if not resp.text or resp.status_code != 200:
                print(f'  第 {page} 页: HTTP {resp.status_code}')
                retry_count += 1
                if retry_count >= max_retries:
                    print(f'  {name}: 重试 {max_retries} 次后放弃, 已保存 {len(videos)} 个视频')
                    save_progress(uid, videos, page - 1)
                    return videos
                wait = 30 * retry_count
                print(f'  等待 {wait}s 后重试 ({retry_count}/{max_retries})...')
                time.sleep(wait)
                continue

            data = resp.json()
            if data.get('code') != 0:
                msg = data.get('message', '')
                print(f'  第 {page} 页 API 错误 (code={data.get("code")}): {msg}')
                if '频繁' in msg or '请求' in msg or data.get('code') == -412:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f'  {name}: 重试 {max_retries} 次后放弃, 已保存 {len(videos)} 个视频')
                        save_progress(uid, videos, page - 1)
                        return videos
                    wait = 60 * retry_count
                    print(f'  [限流] 等待 {wait}s 后重试 ({retry_count}/{max_retries})...')
                    time.sleep(wait)
                    continue
                else:
                    break

            retry_count = 0

            vlist = data['data']['list']['vlist']
            if not vlist:
                print(f'  第 {page} 页: 无视频, 已到末尾')
                break

            new_count = 0
            for v in vlist:
                if v['bvid'] not in existing_bvids:
                    videos.append({
                        'bvid': v['bvid'],
                        'title': v['title'],
                        'title_clean': clean_title(v['title'])
                    })
                    existing_bvids.add(v['bvid'])
                    new_count += 1

            print(f'  第 {page} 页: {len(vlist)} 个 (新增 {new_count}), 累计 {len(videos)} 个')

            # 每页保存进度
            save_progress(uid, videos, page)

            page += 1

            # 限流保护：页间间隔 8 秒
            time.sleep(8)

        except Exception as e:
            print(f'  第 {page} 页 请求异常: {e}')
            retry_count += 1
            if retry_count >= max_retries:
                print(f'  {name}: 重试 {max_retries} 次后放弃, 已保存 {len(videos)} 个视频')
                save_progress(uid, videos, page - 1)
                return videos
            wait = 30 * retry_count
            print(f'  等待 {wait}s 后重试 ({retry_count}/{max_retries})...')
            time.sleep(wait)

    # 全部完成后保存
    save_progress(uid, videos, page)
    print(f'{name}: 完成, 共 {len(videos)} 个视频\n')
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
    parser.add_argument('--match-only', action='store_true', help='跳过 API 获取, 只从已有进度文件做匹配')
    args = parser.parse_args()

    if args.uid and args.uid not in KNOWN_UPS:
        print(f'未知 UID: {args.uid}')
        print(f'已知 UID: {", ".join(KNOWN_UPS.keys())}')
        sys.exit(1)

    uids_to_fetch = [args.uid] if args.uid else list(KNOWN_UPS.keys())

    if not args.match_only:
        print(f'=== 步骤 1: 获取 {len(uids_to_fetch)} 个 UP主 的视频列表 ===\n')

        for uid in uids_to_fetch:
            name = KNOWN_UPS[uid]
            videos, last_page = load_progress(uid)
            start_page = last_page + 1 if last_page > 0 else 1
            fetch_videos(uid, name, start_page)

    # 构建标题映射表（从所有进度文件加载）
    print('\n=== 构建标题映射表 ===')
    title_map = {}

    for uid, name in KNOWN_UPS.items():
        videos, _ = load_progress(uid)
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