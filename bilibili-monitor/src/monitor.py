"""
B站UP主监控主脚本
功能：
1. 获取UP主最新视频列表
2. 过滤掉已处理过的视频（BVID去重）
3. 下载新视频（音频）
4. 下载成功后记录到 data/<name>_downloaded.txt
5. 转写成功后记录到 data/<name>_done_bvid.txt
6. QQ 通知（可选）
"""
import os
import sys
import yaml
import argparse
import time
import subprocess
from pathlib import Path
from datetime import datetime

# 添加脚本目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from get_up_videos import get_video_list, test_cookie
from cookie_utils import load_cookie_from_file
from qq_notify import send_text, get_access_token


def load_config(config_path: str) -> dict:
    """加载YAML配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ─── Checkpoint 文件管理 ───────────────────────────────────────────

def _checkpoint_path(uid: str, suffix: str) -> Path:
    """生成 checkpoint 文件路径（基于 UID，永久唯一）"""
    data_dir = Path(__file__).parent.parent / 'data'
    return data_dir / f'{uid}{suffix}.txt'


def load_checkpoint(uid: str, suffix: str) -> set:
    """加载已记录的 BVID 集合"""
    ck_file = _checkpoint_path(uid, suffix)
    ck_file = os.path.expanduser(ck_file)
    if not os.path.exists(ck_file):
        return set()
    with open(ck_file, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip()}


def append_checkpoint(uid: str, suffix: str, bvids: list):
    """追加 BVID 到 checkpoint 文件"""
    ck_file = _checkpoint_path(uid, suffix)
    ck_file = os.path.expanduser(ck_file)
    os.makedirs(os.path.dirname(ck_file), exist_ok=True)
    with open(ck_file, 'a', encoding='utf-8') as f:
        for b in bvids:
            f.write(b + '\n')


def already_in_checkpoint(uid: str, suffix: str, bvid: str) -> bool:
    """检查 BVID 是否已在指定 checkpoint 中"""
    ck_set = load_checkpoint(uid, suffix)
    return bvid in ck_set


# ─── 辅助函数 ──────────────────────────────────────────────────────

def format_video_info(v: dict) -> str:
    t = v.get('created') or v.get('pubdate') or 0
    created_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(t)) if t else '未知'
    return f"[{created_str}] {v['title']}\n    https://www.bilibili.com/video/{v['bvid']}"


# ─── 核心流程 ──────────────────────────────────────────────────────

def trigger_transcribe(m4a_dir: str, config: dict, uid: str, up_name: str = "", force_asr: bool = False):
    """
    对已下载的 m4a 文件批量转写
    m4a_dir: m4a 文件所在目录
    uid: UP 主 UID（用于关联 checkpoint 文件）
    up_name: UP 主名称（用于按 UP 主分类转写输出）
    force_asr: 强制使用云 ASR（覆盖配置文件设置）

    转写优先级：云 ASR > GPU 远程转写 > 本地 Whisper CPU

    返回: (success_count, failed_count, transcripts_dir)
    """
    # 检查是否使用云 ASR
    asr_config = _load_asr_config()
    use_asr = force_asr or asr_config.get("enabled", False)

    if use_asr:
        return _trigger_transcribe_asr(m4a_dir, config, uid, up_name)

    # 检查是否有 GPU 远程转写服务可用
    gpu_url = os.getenv("GPU_SERVICE_URL", "")
    if gpu_url:
        return _trigger_transcribe_gpu_remote(m4a_dir, config, uid, up_name, gpu_url)

    return _trigger_transcribe_local(m4a_dir, config, uid, up_name)


def _trigger_transcribe_asr(m4a_dir: str, config: dict, uid: str, up_name: str = ""):
    """使用硅基流动云 ASR 转写"""
    from transcribe_asr import process_directory_asr

    api_key = os.getenv('SILICONFLOW_API_KEY', '')
    if not api_key:
        print("  ⚠️ 缺少 SILICONFLOW_API_KEY，无法使用云 ASR，回退到本地 Whisper")
        return _trigger_transcribe_local(m4a_dir, config, uid, up_name)

    model = os.getenv('ASR_MODEL', 'FunAudioLLM/SenseVoiceSmall')

    m4a_path = Path(m4a_dir)
    output_dir = None
    if config.get('transcribe_output_dir', ''):
        up_safe = up_name.replace('/', '_').replace('\\', '_')
        try:
            output_dir = Path(os.path.expanduser(config['transcribe_output_dir'])) / up_safe
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            print(f"  ⚠️ 无法创建转写输出目录 {output_dir}，使用下载目录")
            output_dir = None

    transcripts_dir = str(output_dir or m4a_path)

    print(f"\n  转写 [云ASR]: 调用 process_directory_asr (目录: {m4a_dir})")
    try:
        result = process_directory_asr(
            m4a_dir=str(m4a_path),
            transcripts_dir=str(transcripts_dir),
            uid=uid,
            up_name=up_name,
            api_key=api_key,
            model=model,
            min_duration=60,
        )
    except Exception as e:
        print(f"  ⚠️ 云 ASR 转写异常: {e}")
        return 0, 0, transcripts_dir

    # ── 处理转写结果 ──
    if result.found == 0:
        print(f"  ⚠️ 没有需要转写的文件")
        return 0, 0, transcripts_dir

    # 从输出目录读取新生成的 .txt 文件，提取 BVID
    import re
    saved_bvids = []
    scan_dir = transcripts_dir
    for txt_file in Path(scan_dir).glob("*.txt"):
        m = re.search(r'\[(BV[a-zA-Z0-9]+)\]\.txt$', txt_file.name)
        if m:
            saved_bvids.append(m.group(1))

    # 下载 checkpoint 路径
    dl_set = load_checkpoint(uid, '_downloaded')

    if result.success > 0:
        # 标记成功的 BVID 到 done_bvid
        success_count = len(saved_bvids)
        for bv in saved_bvids:
            append_checkpoint(uid, '_done_bvid', [bv])
        # 从 downloaded 中移除（已转写）
        if saved_bvids and dl_set:
            remaining = dl_set - set(saved_bvids)
            dl_ck_path = os.path.expanduser(_checkpoint_path(uid, '_downloaded'))
            with open(dl_ck_path, 'w') as f:
                for bv in remaining:
                    f.write(bv + '\n')
        print(f"  ✅ 云 ASR 转写完成: {success_count} 个文件 (跳过 {result.skipped} 个)")
        return success_count, result.failed, transcripts_dir

    if result.failed > 0:
        return 0, result.failed, transcripts_dir

    return 0, 0, transcripts_dir


def _trigger_transcribe_gpu_remote(m4a_dir: str, config: dict, uid: str, up_name: str, gpu_url: str):
    """委托 gpu-service 容器进行 GPU 转写（通过 HTTP API）"""
    import requests

    model_size = os.getenv('WHISPER_MODEL', config.get('whisper_model', 'medium'))

    # GPU 远程转写：使用 /app/transcripts 共享目录（bilibili-monitor 和 gpu-service 都挂载）
    up_safe = up_name.replace('/', '_').replace('\\', '_')
    transcripts_dir = f"/app/transcripts/{up_safe}"

    # 确保目录存在
    Path(transcripts_dir).mkdir(parents=True, exist_ok=True)

    # gpu-service 通过共享卷访问相同路径
    gpu_downloads = m4a_dir          # /app/downloads/{up_name} (bilibili-data 卷)
    gpu_transcripts = transcripts_dir  # /app/transcripts/{up_name} (host dir)

    print(f"\n  转写 [GPU远程]: 委托 {gpu_url} (目录: {m4a_dir})")

    try:
        # 1. 提交转写任务
        resp = requests.post(f"{gpu_url}/api/gpu/transcribe", json={
            "downloads": gpu_downloads,
            "transcripts": gpu_transcripts,
            "model_size": model_size,
            "device": "cuda",
        }, timeout=30)

        result = resp.json()
        if not result.get("success"):
            print(f"  ⚠️ GPU 转写提交失败: {result.get('error', '未知')}，回退到本地 Whisper")
            return _trigger_transcribe_local(m4a_dir, config, uid, up_name)

        # 2. 轮询等待完成
        print(f"  ⏳ GPU 转写任务已提交，等待完成...")
        while True:
            time.sleep(5)
            try:
                status_resp = requests.get(f"{gpu_url}/api/gpu/status", timeout=10)
                status = status_resp.json()
                task = status.get("task", {})
                task_status = task.get("status", "unknown")
                progress = task.get("progress", {})

                found = progress.get("found", 0)
                success = progress.get("success", 0)
                failed = progress.get("failed", 0)
                current = progress.get("current", "")

                if found > 0:
                    print(f"    进度: {success + failed}/{found} (当前: {current[:30]})")

                if task_status in ("done", "error", "idle"):
                    break
            except Exception as e:
                print(f"  ⚠️ 轮询 GPU 状态失败: {e}")
                break

        # 3. 处理结果
        if task.get("status") in ("done", "idle"):
            import re
            saved_bvids = []
            scan_dir = Path(transcripts_dir)
            for txt_file in scan_dir.glob("*.txt"):
                m = re.search(r'\[(BV[a-zA-Z0-9]+)\]\.txt$', txt_file.name)
                if m:
                    saved_bvids.append(m.group(1))

            success_count = len(saved_bvids)
            if saved_bvids:
                append_checkpoint(uid, '_done_bvid', saved_bvids)
                dl_set = load_checkpoint(uid, '_downloaded')
                if dl_set:
                    remaining = dl_set - set(saved_bvids)
                    dl_ck_path = os.path.expanduser(_checkpoint_path(uid, '_downloaded'))
                    with open(dl_ck_path, 'w') as f:
                        for bv in remaining:
                            f.write(bv + '\n')

            print(f"  ✅ GPU 远程转写完成: {success_count} 个文件成功, {failed} 个失败")
            return success_count, failed, transcripts_dir
        else:
            print(f"  ⚠️ GPU 转写任务异常: {task.get('status')}")
            return 0, 0, transcripts_dir

    except requests.exceptions.ConnectionError:
        print(f"  ⚠️ GPU 服务不可达 ({gpu_url})，回退到本地 Whisper")
        return _trigger_transcribe_local(m4a_dir, config, uid, up_name)
    except Exception as e:
        print(f"  ⚠️ GPU 远程转写异常: {e}，回退到本地 Whisper")
        return _trigger_transcribe_local(m4a_dir, config, uid, up_name)


def _trigger_transcribe_local(m4a_dir: str, config: dict, uid: str, up_name: str = ""):
    """使用本地 Whisper 转写（原有逻辑）"""
    from transcribe_local import process_directory

    model_size = os.getenv('WHISPER_MODEL', config.get('whisper_model', 'medium'))
    device = os.getenv('WHISPER_DEVICE', config.get('whisper_device', 'cuda'))

    # 设置 HuggingFace 镜像
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

    m4a_path = Path(m4a_dir)
    output_dir = None
    if config.get('transcribe_output_dir', ''):
        up_safe = up_name.replace('/', '_').replace('\\', '_')
        try:
            output_dir = Path(os.path.expanduser(config['transcribe_output_dir'])) / up_safe
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            print(f"  ⚠️ 无法创建转写输出目录 {output_dir}，使用下载目录")
            output_dir = None

    transcripts_dir = str(output_dir if output_dir else m4a_path)

    # 传入 done_bvid 文件路径，供 transcribe_local.py 预检跳过已转写的 m4a
    done_bvid_file = _checkpoint_path(uid, '_done_bvid')
    if not os.path.exists(os.path.expanduser(done_bvid_file)):
        done_bvid_file = None
    else:
        done_bvid_file = Path(os.path.expanduser(done_bvid_file))

    print(f"\n  转写: 调用 process_directory (目录: {m4a_dir})")
    try:
        result = process_directory(
            m4a_path,
            model_size=model_size,
            device=device,
            delete_audio=True,
            output_dir=output_dir,
            done_bvid_file=done_bvid_file,
            min_duration=60,
        )
    except Exception as e:
        print(f"  ⚠️ 转写异常: {e}")
        return 0, 0, transcripts_dir

    # ── 处理转写结果 ──
    if result.no_file:
        print(f"  ⚠️ 目录为空，无 m4a 文件")
        return 0, 0, transcripts_dir

    # 从输出目录读取新生成的 .txt 文件，提取 BVID
    import re
    saved_bvids = []
    scan_dir = output_dir if output_dir else m4a_path
    for txt_file in scan_dir.glob("*.txt"):
        m = re.search(r'\[(BV[a-zA-Z0-9]+)\]\.txt$', txt_file.name)
        if m:
            saved_bvids.append(m.group(1))

    # 下载 checkpoint 路径
    dl_set = load_checkpoint(uid, '_downloaded')

    if result.all_success:
        # 全部成功：把 downloaded 中这批 BVID 标记到 done_bvid
        success_count = len(saved_bvids)
        for bv in saved_bvids:
            append_checkpoint(uid, '_done_bvid', [bv])
        # 从 downloaded 中移除（已转写）
        if saved_bvids and dl_set:
            remaining = dl_set - set(saved_bvids)
            dl_ck_path = os.path.expanduser(_checkpoint_path(uid, '_downloaded'))
            with open(dl_ck_path, 'w') as f:
                for bv in remaining:
                    f.write(bv + '\n')
        print(f"  ✅ 转写完成: {success_count} 个文件")
        return success_count, 0, transcripts_dir

    if result.has_work:
        # 部分失败：只标记成功的
        success_count = len(saved_bvids)
        for bv in saved_bvids:
            append_checkpoint(uid, '_done_bvid', [bv])
        return success_count, result.failed, transcripts_dir

    # 异常情况
    return 0, 0, transcripts_dir


def _load_asr_config() -> dict:
    """加载 ASR 设置（从共享卷读取）"""
    import json
    data_dir = os.getenv("BILIBILI_DATA_DIR", "")
    if not data_dir:
        data_dir = str(Path(__file__).parent.parent / "data")

    settings_file = Path(data_dir) / ".asr_config" / "settings.json"

    if settings_file.exists():
        try:
            with open(settings_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {"enabled": False, "monthly_budget_minutes": 60}


def notify_new_videos(up_name: str, videos: list, config: dict):
    """发送 QQ 通知"""
    notify_target = config.get('notify_target', '')
    if not notify_target or not notify_target.startswith('qq:'):
        return
    openid = notify_target[3:].strip()
    if not openid or openid.startswith('YOUR_'):
        return

    to_show = videos[:5]
    lines = [f"📺 【{up_name}】发现 {len(videos)} 个新视频：", ""]
    for v in to_show:
        t = v.get('created') or v.get('pubdate') or 0
        ts = time.strftime('%m-%d %H:%M', time.localtime(t)) if t else '未知时间'
        lines.append(f"▪️ {v['title']}")
        lines.append(f"  {ts} | https://www.bilibili.com/video/{v['bvid']}")
        lines.append("")
    if len(videos) > 5:
        lines.append(f"...还有 {len(videos) - 5} 个")

    message = '\n'.join(lines)
    try:
        token = get_access_token()
        send_text(openid, message, token=token)
        print(f"  ✅ QQ 通知已发送")
    except Exception as e:
        print(f"  ⚠️ QQ 通知失败: {e}")


def main():
    parser = argparse.ArgumentParser(description='监控B站UP主新视频')
    parser.add_argument('config', help='配置文件路径 (YAML)')
    parser.add_argument('--dry-run', action='store_true', help='只查看新视频，不下载')
    parser.add_argument('--force', action='store_true', help='强制重新下载已处理过的视频')
    parser.add_argument('--no-transcribe', action='store_true', help='跳过自动转写')
    parser.add_argument('--no-notify', action='store_true', help='跳过 QQ 通知')
    parser.add_argument('--metadata-only', action='store_true', help='只获取元数据写入DuckDB，不下载不转写')
    parser.add_argument('--max-videos', type=int, default=0, help='最多处理视频数（0=不限制）')
    parser.add_argument('--asr', action='store_true', help='强制使用云 ASR 转写（覆盖配置文件设置）')
    args = parser.parse_args()

    config = load_config(args.config)
    up_name = config.get('name', '未知UP主')
    uid = config['uid']
    cookie_file = os.path.expanduser(config['cookie_file'])
    download_root = os.path.expanduser(config.get('download_root', '~/B站监控'))
    domain = config.get('domain', 'emotional')

    print(f"{'='*60}")
    print(f"开始监控: {up_name} (UID: {uid})")
    print(f"{'='*60}\n")

    # ── Cookie ──
    try:
        cookies = load_cookie_from_file(cookie_file)
        print(f"✓ Cookie加载成功")
    except Exception as e:
        print(f"✗ Cookie加载失败: {e}")
        sys.exit(1)

    # ── Cookie 有效性校验 ──
    print("正在校验 Cookie 有效性...")
    cookie_ok, cookie_uname = test_cookie(cookies)
    if not cookie_ok:
        print(f"✗ Cookie 已失效: {cookie_uname}")
        # 发送 QQ 通知
        notify_target = config.get('notify_target', '')
        if notify_target and notify_target.startswith('qq:'):
            openid = notify_target[3:].strip()
            if openid and not openid.startswith('YOUR_'):
                try:
                    token = get_access_token()
                    msg = (f"⚠️ 【B站监控告警】\n"
                           f"UP主「{up_name}」Cookie 已失效！\n"
                           f"错误原因：{cookie_uname}\n"
                           f"请尽快更新 Cookie 文件：~/.bilibili/cookie.txt\n"
                           f"本次抓取已暂停。")
                    send_text(openid, msg, token=token)
                    print(f"  ✅ 已通知 QQ")
                except Exception as e:
                    print(f"  ⚠️ QQ 通知失败: {e}")
        sys.exit(1)
    print(f"✓ Cookie 有效（账号：{cookie_uname}）\n")

    # ── Checkpoint 初始化 ──
    done_bvid_set  = load_checkpoint(uid, '_done_bvid')
    downloaded_set = load_checkpoint(uid, '_downloaded')
    is_new_up = (len(done_bvid_set) == 0 and len(downloaded_set) == 0)
    print(f"已处理视频数: {len(done_bvid_set)} (done_bvid), {len(downloaded_set)} (已下载待转写)")
    print(f"{'(新 UP，全量扫描)' if is_new_up else '(增量扫描)'}\n")

    # ── 获取视频列表 ──
    max_count = 9999 if is_new_up else 30
    if args.max_videos > 0:
        max_count = min(max_count, args.max_videos)
    print(f"正在获取视频列表{'（全量）' if is_new_up else '（第一页）'}...")
    try:
        videos = get_video_list(uid, cookies, max_count=max_count)
        print(f"✓ 获取到 {len(videos)} 个视频\n")
    except Exception as e:
        print(f"✗ 获取视频列表失败: {e}")
        sys.exit(1)

    # ── 过滤新视频 ──
    if args.force:
        new_videos = videos
    else:
        new_videos = [v for v in videos
                      if v['bvid'] not in done_bvid_set
                      and v['bvid'] not in downloaded_set]

    if not new_videos:
        print("没有发现新视频")
        # 检查是否有已下载但未转写的视频，如果有则继续转写流程
        pending = downloaded_set - done_bvid_set
        if pending and not args.no_transcribe:
            print(f"但有 {len(pending)} 个已下载未转写的视频，进入转写流程")
            newly_downloaded = []
            # 跳过下载，直接进入转写
            safe_name = up_name.replace('/', '_').replace('\\', '_')
            output_dir = os.path.join(download_root, safe_name)
        else:
            sys.exit(0)
    else:
        print(f"发现 {len(new_videos)} 个新视频:\n")
        for i, v in enumerate(new_videos, 1):
            print(f"  {i}. {format_video_info(v)}")
        print()

        if args.dry_run:
            print("(--dry-run 模式，只显示不下载)")
            sys.exit(0)

        # ── metadata-only 模式：只写入 DuckDB，不下载不转写 ──
        if args.metadata_only:
            from db_writer import DBWriter

            print("\n(--metadata-only 模式，写入 DuckDB)")
            with DBWriter() as db:
                video_records = []
                for v in new_videos:
                    pub_date = None
                    t = v.get('created') or v.get('pubdate') or 0
                    if t:
                        pub_date = datetime.fromtimestamp(t).date()

                    video_records.append({
                        'bvid': v['bvid'],
                        'up_name': up_name,
                        'up_uid': uid,
                        'title': v['title'],
                        'publish_date': pub_date,
                        'category': v.get('tname', ''),
                        'duration': v.get('duration', 0),
                        'summary': None,
                        'tags': v.get('tags', ''),
                        'domain': domain,
                    })

                success = db.insert_videos(video_records)
                print(f"  写入视频元数据: {success}/{len(video_records)} 成功")
                db.update_up_info(
                    uid=uid,
                    name=up_name,
                    total_videos=len(videos),
                    config_file=args.config,
                )
                print(f"  更新 UP 主信息: {up_name} (共 {len(videos)} 个视频)")

            sys.exit(0)

        # ── 下载 ──
        from download_videos import download_video

        safe_name = up_name.replace('/', '_').replace('\\', '_')
        output_dir = os.path.join(download_root, safe_name)
        os.makedirs(output_dir, exist_ok=True)

        newly_downloaded = []   # [(bvid, title), ...]
        for i, v in enumerate(new_videos, 1):
            bvid = v['bvid']
            title = v['title']
            url = f"https://www.bilibili.com/video/{bvid}"

            print(f"[{i}/{len(new_videos)}] 下载: {title}")
            ok = download_video(url, output_dir, cookie_file)

            if ok:
                newly_downloaded.append((bvid, title))
                append_checkpoint(uid, '_downloaded', [bvid])
                print(f"  ✓ 完成 (已记入 downloaded)")
            else:
                print(f"  ✗ 失败")

            if i < len(new_videos):
                time.sleep(3)

        print(f"\n{'='*60}")
        print(f"下载完成: {len(newly_downloaded)}/{len(new_videos)} 成功")
        print(f"{'='*60}")

    # ── 转写 ──
    # 检查是否有已下载但未转写的视频（上次转写失败的情况）
    dl_set = load_checkpoint(uid, '_downloaded')
    done_set = load_checkpoint(uid, '_done_bvid')
    pending_transcribe = dl_set - done_set

    if (newly_downloaded or pending_transcribe) and not args.no_transcribe:
        # 转写前预检：把 downloaded 中已在 done_bvid 的 BVID 移走（避免重复转写）
        already_done = dl_set & done_set
        if already_done:
            print(f"  [预检] 从 downloaded 移除 {len(already_done)} 个已转写 BVID")
            remaining = dl_set - already_done
            dl_ck_path = os.path.expanduser(_checkpoint_path(uid, '_downloaded'))
            with open(dl_ck_path, 'w') as f:
                for bv in remaining:
                    f.write(bv + '\n')

        if pending_transcribe and not newly_downloaded:
            print(f"\n  发现 {len(pending_transcribe)} 个已下载但未转写的视频，触发补转写")

        transcribe_ok, transcribe_failed, actual_transcripts_dir = trigger_transcribe(output_dir, config, uid, up_name, force_asr=args.asr)
        print(f"  转写结果: {transcribe_ok} 成功, {transcribe_failed} 失败")

        # ── 精炼 + 入库（转写成功后） ──
        if transcribe_ok > 0:
            from post_transcribe import process_transcripts

            # 准备视频元数据（用于入库时附加）
            videos_info = {}
            for v in new_videos:
                pub_date = None
                t = v.get('created') or v.get('pubdate') or 0
                if t:
                    pub_date = datetime.fromtimestamp(t).date()
                videos_info[v['bvid']] = {
                    'title': v['title'],
                    'publish_date': pub_date,
                    'category': v.get('tname', ''),
                    'duration': v.get('duration', 0),
                }

            # 确定转写输出目录（优先使用转写实际输出目录）
            if actual_transcripts_dir and Path(actual_transcripts_dir).exists() and list(Path(actual_transcripts_dir).glob("*.txt")):
                scan_dir = actual_transcripts_dir
            else:
                trans_output = config.get('transcribe_output_dir', '')
                if trans_output:
                    up_safe = up_name.replace('/', '_').replace('\\', '_')
                    scan_dir = os.path.join(os.path.expanduser(trans_output), up_safe)
                else:
                    scan_dir = output_dir

            # GPU 远程转写时，txt 文件在 /app/transcripts/ 下，如果 scan_dir 没有 txt 则回退
            if not list(Path(scan_dir).glob("*.txt")):
                up_safe = up_name.replace('/', '_').replace('\\', '_')
                gpu_scan = f"/app/transcripts/{up_safe}"
                if Path(gpu_scan).exists() and list(Path(gpu_scan).glob("*.txt")):
                    scan_dir = gpu_scan

            print(f"\n  精炼 + 入库: 扫描 {scan_dir}")
            try:
                stats = process_transcripts(
                    transcript_dir=scan_dir,
                    up_name=up_name,
                    up_uid=uid,
                    videos_info=videos_info,
                    domain=domain,
                )
                print(f"  入库完成: {stats['db_ok']} DuckDB, {stats['chroma_ok']} ChromaDB, {stats['refined']} 精炼")
            except Exception as e:
                print(f"  ⚠️ 精炼+入库异常: {e}")

    # ── QQ 通知（下载成功后） ──
    if newly_downloaded and not args.no_notify:
        notify_new_videos(up_name, new_videos, config)


if __name__ == '__main__':
    main()
