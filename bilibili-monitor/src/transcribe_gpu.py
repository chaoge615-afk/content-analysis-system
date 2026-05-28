#!/usr/bin/env python3
"""
GPU 转录脚本 — 用于开发机 (RTX 4060) 配合飞牛 Sync 工作流

工作方式：
    1. 扫描 downloads/ 中的 .m4a 文件
    2. 检查 transcripts/ 中是否已有对应 .txt（按 BVID 匹配）
    3. 未转写的用 GPU (CUDA) 转录，写入 transcripts/
    4. 增量处理：已转写的自动跳过

用法：
    python transcribe_gpu.py --downloads D:\sync\downloads --transcripts D:\sync\transcripts
    python transcribe_gpu.py --downloads D:\sync\downloads --transcripts D:\sync\transcripts --model-size medium
"""
import argparse
import re
import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel


def format_duration(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}m{s:02d}s"


def extract_bvid(filename: str) -> str | None:
    """从文件名中提取 BVID，如 '标题 [BV1xx...].m4a'"""
    m = re.search(r'\[(BV[a-zA-Z0-9]+)\]', filename)
    return m.group(1) if m else None


def get_audio_duration(audio_path: Path) -> float:
    """用 ffprobe 获取音频时长（秒）"""
    import subprocess
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, timeout=10,
    )
    try:
        return float(probe.stdout.strip())
    except Exception:
        return 0.0


def build_existing_index(transcripts_dir: Path) -> set[str]:
    """扫描 transcripts/ 中已有 txt 文件，提取 BVID 集合"""
    existing = set()
    if not transcripts_dir.exists():
        return existing
    for txt_file in transcripts_dir.glob("*.txt"):
        bvid = extract_bvid(txt_file.name)
        if bvid:
            existing.add(bvid)
    return existing


def process(
    downloads_dir: Path,
    transcripts_dir: Path,
    model_size: str = "small",
    device: str = "cuda",
    min_duration: int = 60,
    checkpoint_file: Path | None = None,
):
    m4a_files = sorted(downloads_dir.glob("*.m4a"))
    if not m4a_files:
        print("📭 downloads/ 中没有 .m4a 文件，跳过")
        return

    transcripts_dir.mkdir(parents=True, exist_ok=True)

    # 加载已转写的 BVID
    existing = build_existing_index(transcripts_dir)
    print(f"  已转写: {len(existing)} 个")

    # 加载本地 checkpoint（防止飞牛同步延迟导致重复转写）
    done_bvids: set[str] = set()
    if checkpoint_file and checkpoint_file.exists():
        done_bvids = {line.strip() for line in open(checkpoint_file, encoding='utf-8') if line.strip()}

    # 过滤待处理文件
    to_transcribe: list[tuple[Path, str]] = []
    skipped = 0
    for m4a in m4a_files:
        bvid = extract_bvid(m4a.name)
        if bvid and (bvid in existing or bvid in done_bvids):
            skipped += 1
            continue
        to_transcribe.append((m4a, bvid or ""))

    if skipped:
        print(f"  ⏭️ 跳过 {skipped} 个已转写的")
    if not to_transcribe:
        print("✅ 所有文件均已转写，无需处理")
        return

    print(f"\n🎙️ 待转写: {len(to_transcribe)} 个文件")

    # 加载模型（GPU + float16）
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"  加载模型: {model_size} (device={device}, compute={compute_type})")
    t0 = time.time()
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print(f"  模型加载耗时: {time.time() - t0:.1f}s\n")

    success = 0
    failed = 0
    total_duration = 0.0
    total_transcribe_time = 0.0

    for m4a, bvid in to_transcribe:
        print(f"▶ {m4a.name}")
        try:
            duration = get_audio_duration(m4a)
            if 0 < duration < min_duration:
                print(f"  ⏭️ 时长 {format_duration(duration)} < {min_duration}s，跳过")
                continue
            print(f"  时长: {format_duration(duration)}")
            total_duration += duration

            t1 = time.time()
            segments, _ = model.transcribe(str(m4a), language="zh")
            text_parts = [(seg.text or "").strip() for seg in segments if (seg.text or "").strip()]
            text = "\n".join(text_parts)
            elapsed = time.time() - t1
            total_transcribe_time += elapsed
            rt_factor = elapsed / duration if duration > 0 else 0

            # 生成 txt 文件名（保持与 monitor.py 一致的命名规则）
            title = m4a.stem.rsplit(" [", 1)[0] if " [" in m4a.stem else m4a.stem
            txt_name = f"{title} [{bvid}].txt" if bvid else f"{m4a.stem}.txt"
            txt_path = transcripts_dir / txt_name
            txt_path.write_text(text + "\n", encoding="utf-8")
            print(f"  ✅ {txt_name} ({len(text)} 字, {elapsed:.1f}s, RTF={rt_factor:.2f})")

            # 写入 checkpoint
            if checkpoint_file and bvid:
                with open(checkpoint_file, "a", encoding="utf-8") as f:
                    f.write(bvid + "\n")

            # 释放显存碎片
            if device == "cuda":
                try:
                    import torch
                    torch.cuda.empty_cache()
                except ImportError:
                    pass

            success += 1

        except Exception as e:
            failed += 1
            print(f"  ❌ 失败: {e}")

    # 汇总
    print(f"\n{'='*50}")
    print(f"✅ 成功: {success}  |  ❌ 失败: {failed}")
    if total_duration > 0:
        print(f"总音频: {format_duration(total_duration)}  |  转录耗时: {total_transcribe_time:.1f}s  |  平均 RTF: {total_transcribe_time/total_duration:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU 转录脚本（飞牛 Sync 工作流）")
    parser.add_argument("--downloads", required=True, type=Path,
                        help="downloads/ 目录（飞牛同步过来的音频文件）")
    parser.add_argument("--transcripts", required=True, type=Path,
                        help="transcripts/ 目录（转录结果，同步回 NAS）")
    parser.add_argument("--model-size", "-m", default="small",
                        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"])
    parser.add_argument("--device", "-d", default="cuda", choices=["cpu", "cuda"])
    parser.add_argument("--min-duration", type=int, default=60,
                        help="跳过时长小于此秒数的音频（默认60）")
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="本地 checkpoint 文件路径（记录已转写 BVID）")
    args = parser.parse_args()

    downloads_dir = args.downloads.expanduser().resolve()
    transcripts_dir = args.transcripts.expanduser().resolve()

    if not downloads_dir.is_dir():
        print(f"❌ downloads 目录不存在: {downloads_dir}")
        sys.exit(1)

    checkpoint = args.checkpoint.expanduser().resolve() if args.checkpoint else None

    process(
        downloads_dir=downloads_dir,
        transcripts_dir=transcripts_dir,
        model_size=args.model_size,
        device=args.device,
        min_duration=args.min_duration,
        checkpoint_file=checkpoint,
    )