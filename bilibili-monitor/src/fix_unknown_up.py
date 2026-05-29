"""
修复 unknown 视频归属
用 yt-dlp 查询每个 unknown 视频的真实 UP主
"""
import os
import sys
import time
import yt_dlp
import duckdb

DB_PATH = os.getenv("DUCKDB_PATH", "/app/data/content.db")

# 已知 UP主 UID → 名称映射
KNOWN_UPS = {
    "3546912280021515": "恋爱教头桃姐",
    "410110370": "是你的安佳佳呀",
    "3493258856499557": "啊柚的碎碎念",
    "3546767933049757": "夹性学姐在这",
}


def fix_unknown():
    conn = duckdb.connect(DB_PATH)
    rows = conn.execute(
        "SELECT bvid FROM video_meta WHERE up_name = 'unknown' ORDER BY bvid"
    ).fetchall()

    total = len(rows)
    print(f"找到 {total} 个 unknown 视频，开始查询...")

    matched = 0
    new_up = 0
    failed = 0
    skipped = 0

    # Cookie 文件路径
    cookie_file = os.getenv("BILIBILI_COOKIE_FILE", "/root/.bilibili/cookie.txt")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    if os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file

    for i, (bvid,) in enumerate(rows, 1):
        url = f"https://www.bilibili.com/video/{bvid}"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            uploader = info.get("uploader", "")
            uploader_id = str(info.get("uploader_id", ""))

            if uploader_id in KNOWN_UPS:
                matched_name = KNOWN_UPS[uploader_id]
                conn.execute(
                    "UPDATE video_meta SET up_name = ?, up_uid = ? WHERE bvid = ?",
                    [matched_name, uploader_id, bvid],
                )
                matched += 1
                print(f"[{i}/{total}] {bvid} → {matched_name} ✓")
            elif uploader and uploader != "unknown":
                conn.execute(
                    "UPDATE video_meta SET up_name = ?, up_uid = ? WHERE bvid = ?",
                    [uploader, uploader_id, bvid],
                )
                new_up += 1
                print(f"[{i}/{total}] {bvid} → {uploader} (新UP主)")
            else:
                skipped += 1
                print(f"[{i}/{total}] {bvid} → 无法识别")

        except Exception as e:
            failed += 1
            err_msg = str(e)[:60]
            print(f"[{i}/{total}] {bvid} → 查询失败: {err_msg}")

        # 限流保护
        if i % 50 == 0:
            print(f"  进度: {i}/{total} (匹配:{matched} 新UP主:{new_up} 跳过:{skipped} 失败:{failed})")
            time.sleep(3)
        else:
            time.sleep(0.5)

    conn.commit()
    conn.close()

    print(f"\n{'='*50}")
    print(f"修复完成: {total} 个视频")
    print(f"  匹配已知UP主: {matched}")
    print(f"  发现新UP主: {new_up}")
    print(f"  无法识别: {skipped}")
    print(f"  查询失败: {failed}")


if __name__ == "__main__":
    fix_unknown()
