#!/usr/bin/env python3
"""
多UP主聚合监控
扫描 config/ 下所有配置文件，逐一运行，汇总报告
"""
import argparse
import subprocess
import sys
import time
import yaml
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MONITOR_SCRIPT = SCRIPT_DIR / "monitor.py"

MAX_CONCURRENT_TRANSCRIBE = 2  # 最多同时转写几个 UP


def find_all_configs():
    """扫描 config/ 下所有 .yaml 文件"""
    config_dir = SCRIPT_DIR.parent / "config"
    return sorted(config_dir.glob("*.yaml"))


def run_single(config_path: Path, dry_run: bool, no_transcribe: bool, no_notify: bool, metadata_only: bool = False, max_videos: int = 0):
    """运行单个配置的监控，返回 (name, success, new_count, message, output)"""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    name = cfg.get("name", config_path.stem)

    cmd = [
        sys.executable, str(MONITOR_SCRIPT),
        str(config_path),
        "--dry-run" if dry_run else "",
        "--no-transcribe" if no_transcribe else "",
        "--no-notify" if no_notify else "",
        "--metadata-only" if metadata_only else "",
        f"--max-videos={max_videos}" if max_videos > 0 else "",
    ]
    cmd = [c for c in cmd if c]

    # start_new_session=True 让子进程独立，不受 monitor_all 退出影响
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    try:
        stdout, stderr = proc.communicate(timeout=7200)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        return name, False, 0, f"  ❌ {name} — 异常超时", ""

    output = stdout + stderr

    # 解析输出中的"发现 N 个新视频"行
    new_count = 0
    downloaded = False
    for line in output.splitlines():
        if "✓ 完成" in line or "下载完成:" in line:
            downloaded = True
        elif line.strip().startswith("发现 ") and "个新视频" in line:
            parts = line.strip().split()
            for i, p in enumerate(parts):
                if p == "发现" and i + 1 < len(parts):
                    try:
                        new_count = int(parts[i + 1])
                    except ValueError:
                        pass

    if proc.returncode == 0:
        if dry_run:
            msg = f"  ✅ {name} — 发现 {new_count} 个新视频"
        elif downloaded:
            msg = f"  ✅ {name} — 下载完成，新增 {new_count} 个"
        else:
            msg = f"  ✅ {name} — 无新视频"
    else:
        msg = f"  ❌ {name} — 退出码 {proc.returncode}\n{output[-300:]}"
        if not output:
            msg += "\n(无输出，可能被系统信号终止)"

    return name, proc.returncode == 0, new_count, msg, output


def run_batch(configs: list, dry_run: bool, no_transcribe: bool, no_notify: bool, metadata_only: bool = False, max_videos: int = 0):
    """
    批量运行一组配置，同步等待全部完成。
    返回 [(name, success, new_count, msg, output), ...]
    """
    results = []
    for cfg in configs:
        print(f"\n处理: {cfg.name} ...", end=" ", flush=True)
        r = run_single(cfg, dry_run, no_transcribe, no_notify, metadata_only, max_videos)
        results.append(r)
        print("done")
    return results


def main():
    parser = argparse.ArgumentParser(description="多UP主聚合监控")
    parser.add_argument('--dry-run', action='store_true', help='只查看新视频，不下载')
    parser.add_argument('--no-transcribe', action='store_true', help='跳过自动转写')
    parser.add_argument('--no-notify', action='store_true', help='跳过 QQ 通知')
    parser.add_argument('--metadata-only', action='store_true', help='只获取元数据写入DuckDB，不下载不转写')
    parser.add_argument('--max-videos', type=int, default=0, help='每个UP最多处理视频数（0=不限制）')
    parser.add_argument('--up', help='只运行指定UP主（配置名，如 an Jiajia）')
    args = parser.parse_args()

    configs = find_all_configs()
    if not configs:
        print("❌ config/ 目录下没有找到配置文件")
        sys.exit(1)

    if args.up:
        configs = [c for c in configs if args.up in c.stem]
        if not configs:
            print(f"❌ 没有找到包含 '{args.up}' 的配置文件")
            sys.exit(1)

    print(f"{'='*60}")
    print(f"B站多UP主聚合监控")
    print(f"配置文件: {[c.name for c in configs]}")
    print(f"模式: {'dry-run' if args.dry_run else '下载+转写'}")
    print(f"{'='*60}")

    # ── 分批：下载阶段可以全量并行，转写阶段最多 MAX_CONCURRENT_TRANSCRIBE 个 UP 同时跑
    if args.no_transcribe or args.dry_run or args.metadata_only:
        # 无转写场景：全部串行跑即可
        batched = [configs]
    else:
        # 按批次分组，每批最多 MAX_CONCURRENT_TRANSCRIBE 个 UP
        batched = []
        for i in range(0, len(configs), MAX_CONCURRENT_TRANSCRIBE):
            batched.append(configs[i:i + MAX_CONCURRENT_TRANSCRIBE])
        print(f"\n📦 分 {len(batched)} 批执行（每批最多 {MAX_CONCURRENT_TRANSCRIBE} 个 UP 并发转写）")

    all_results = []
    for batch_idx, batch in enumerate(batched, 1):
        if len(batched) > 1:
            print(f"\n{'='*60}")
            print(f"第 {batch_idx}/{len(batched)} 批: {[c.name for c in batch]}")
            print(f"{'='*60}")
        batch_results = run_batch(batch, args.dry_run, args.no_transcribe, args.no_notify, args.metadata_only, args.max_videos)
        all_results.extend(batch_results)

        # 上一批与下一批之间稍作停顿，让 GPU 显存释放
        if batch_idx < len(batched):
            print("\n⏳ 等待 GPU 显存回收...")
            time.sleep(5)

    # 汇总报告
    total_new = sum(r[2] for r in all_results)
    ok_count = sum(1 for r in all_results if r[1])

    print(f"\n{'='*60}")
    print(f"📊 汇总报告")
    print(f"{'='*60}")
    for r in all_results:
        print(r[3])
    print(f"\n{'='*60}")
    print(f"总计: {ok_count}/{len(configs)} 个UP主成功，新增 {total_new} 个视频")

    # ── 收尾：清理 downloaded.txt 中已转写的 BVID（防止历史残留导致死锁）
    if not args.dry_run:
        print(f"\n🧹 清理 downloaded checkpoint...")
        for cfg in configs:
            with open(cfg, encoding="utf-8") as f:
                cfg_data = yaml.safe_load(f)
            uid = cfg_data.get("uid", cfg.stem)
            dl_file = SCRIPT_DIR.parent / "data" / f"{uid}_downloaded.txt"
            done_file = SCRIPT_DIR.parent / "data" / f"{uid}_done_bvid.txt"
            if dl_file.exists():
                dl_bvids = {l.strip() for l in dl_file.open() if l.strip()}
                done_bvids = (
                    {l.strip() for l in done_file.open() if l.strip()}
                    if done_file.exists()
                    else set()
                )
                stale = dl_bvids & done_bvids
                if stale:
                    clean = dl_bvids - done_bvids
                    dl_file.write_text("\n".join(sorted(clean)) + "\n")
                    print(f"  从 {dl_file.name} 移除 {len(stale)} 个已转写 BVID")

    if args.dry_run and total_new > 0:
        print("\n💡 确认后运行（不含 --dry-run）开始下载和转写")


if __name__ == '__main__':
    main()