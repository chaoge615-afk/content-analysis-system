#!/usr/bin/env python3
"""
本地转写：直接对已有的 m4a 文件做转写，不重新下载
用法：
    python transcribe_local.py "~/B站监控/转写结果"
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from faster_whisper import WhisperModel


@dataclass
class TranscribeResult:
    """
    转写结果明细
    found:     找到的 m4a 文件数
    success:   成功转写的文件数
    failed:    失败的文件数（含异常）
    no_file:   是否无 m4a 文件（目录为空）
    errors:    错误信息列表
    """
    found: int = 0
    success: int = 0
    failed: int = 0
    no_file: bool = False
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def all_success(self) -> bool:
        """全部成功（无失败）"""
        return self.found > 0 and self.failed == 0

    @property
    def has_work(self) -> bool:
        """有文件待处理（找到了 m4a）"""
        return self.found > 0


def probe_duration(audio_path: Path) -> float:
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, timeout=10
    )
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def format_duration(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}m{s:02d}s"


def transcribe_m4a(audio_path: Path, model_size: str, device: str, min_duration: int = 60):
    """对单个 m4a 转写，返回 (纯文本, model) 或 (None, None) 如果时长不足"""
    import subprocess as _sp

    # 先探测时长，不足跳过
    probe = _sp.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, timeout=10
    )
    try:
        duration = float(probe.stdout.strip())
    except Exception:
        duration = 0.0

    if duration > 0 and duration < min_duration:
        print(f"    ⏭️ 时长 {format_duration(duration)} < {min_duration}s，跳过")
        return None, None

    print(f"    时长: {format_duration(duration)}")

    # faster-whisper 配置
    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    # 转写
    segments, info = model.transcribe(str(audio_path), language="zh")

    full_text_parts = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            full_text_parts.append(text)

    text = "\n".join(full_text_parts)
    return text, model


def simplify(text: str) -> str:
    try:
        from opencc import OpenCC
        cc = OpenCC("t2s")
        return cc.convert(text)
    except Exception:
        return text


def sanitize_filename(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace("\0", "_")


def process_directory(
    input_dir: Path,
    model_size: str = "medium",
    device: str = "cuda",
    delete_audio: bool = True,
    output_dir: Optional[Path] = None,
    done_bvid_file: Optional[Path] = None,
    min_duration: int = 60,
) -> TranscribeResult:
    m4a_files = sorted(input_dir.glob("*.m4a"))

    if not m4a_files:
        return TranscribeResult(no_file=True)

    # ── 预检：done_bvid 过滤 ────────────────────────────────────────
    skip_bvids: set = set()
    if done_bvid_file and done_bvid_file.exists():
        skip_bvids = {line.strip() for line in open(done_bvid_file, encoding='utf-8')
                      if line.strip()}
        print(f"  已完成 BVID 数: {len(skip_bvids)}，将跳过已转写的 m4a")

    # 过滤掉已在 done_bvid 中的 m4a
    to_transcribe = []
    skipped_count = 0
    for m4a in m4a_files:
        m = re.search(r'\[(BV[a-zA-Z0-9]+)\]\.m4a$', m4a.name)
        if m and m.group(1) in skip_bvids:
            # 已在 done_bvid 中，直接删除 m4a
            m4a.unlink()
            skipped_count += 1
        else:
            to_transcribe.append(m4a)

    if skipped_count:
        print(f"  🗑️ 跳过 {skipped_count} 个已转写的 m4a（已删除）")

    if not to_transcribe:
        return TranscribeResult(no_file=True)  # 所有 m4a 都已跳过

    print(f"发现 {len(to_transcribe)} 个待转写 m4a 文件")

    result = TranscribeResult(found=len(to_transcribe))
    out_parent = (output_dir or input_dir).resolve()
    out_parent.mkdir(parents=True, exist_ok=True)

    for m4a in to_transcribe:
        print(f"\n转写: {m4a.name}")
        try:
            text, model = transcribe_m4a(m4a, model_size, device, min_duration=min_duration)

            # 时长不足时 transcribe_m4a 返回 (None, None)
            if text is None:
                if delete_audio:
                    m4a.unlink()
                    print(f"    🗑️ 已删除音频（时长不足）")
                result.success += 1
                continue
            text = simplify(text)

            # 从文件名提取 BVID 和标题
            bvid = None
            m = re.search(r'\[(BV[a-zA-Z0-9]+)\]\.m4a$', m4a.name)
            if m:
                bvid = m.group(1)
                title = m4a.stem.rsplit(" [", 1)[0]
                title = sanitize_filename(title)
                txt_name = f"{title} [{bvid}].txt"
            else:
                txt_name = m4a.stem + ".txt"

            txt_path = out_parent / txt_name
            txt_path.write_text(text + "\n", encoding="utf-8")
            print(f"    ✅ 已保存: {txt_path.name} ({len(text)} 字)")

            if delete_audio:
                m4a.unlink()
                print(f"    🗑️ 已删除音频")

            # 转写成功后立即追加到 done_bvid（增量 checkpoint，防止崩溃后重复转写）
            if bvid and done_bvid_file:
                try:
                    with open(done_bvid_file, "a", encoding="utf-8") as f:
                        f.write(bvid + "\n")
                    print(f"    📝 已追加 done_bvid: {bvid}")
                except Exception as e:
                    print(f"    ⚠️ done_bvid 追加失败: {e}")

            # 释放显存，避免碎片累积
            if device == 'cuda':
                import torch
                torch.cuda.empty_cache()

            result.success += 1

        except Exception as e:
            result.failed += 1
            result.errors.append(f"{m4a.name}: {e}")
            print(f"    ❌ 失败: {e}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="对本地 m4a 文件批量转写")
    parser.add_argument("input_dir", help="m4a 文件所在目录")
    parser.add_argument("--model-size", "-m", default="medium",
                        choices=["tiny","base","small","medium","large-v2","large-v3"])
    parser.add_argument("--device", "-d", default="cuda", choices=["cpu", "cuda"])
    parser.add_argument("--keep-audio", action="store_true", help="保留 m4a 文件")
    parser.add_argument("--output-dir", "-o", type=Path, default=None,
                        help="txt 输出目录（默认同 m4a 目录）")
    parser.add_argument("--done-bvid", type=Path, default=None,
                        help="跳过已在此文件中记录 BVID 的 m4a 文件（直接删除）")
    parser.add_argument("--min-duration", type=int, default=60,
                        help="跳过时长小于此秒数的音频（默认60）")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"目录不存在: {input_dir}")
        sys.exit(1)

    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else None
    done_bvid = args.done_bvid.expanduser().resolve() if args.done_bvid else None
    result = process_directory(
        input_dir,
        args.model_size,
        args.device,
        delete_audio=not args.keep_audio,
        output_dir=output_dir,
        done_bvid_file=done_bvid,
        min_duration=args.min_duration,
    )

    print(f"\n{'='*50}")
    if result.no_file:
        print("⚠️ 目录中未找到 .m4a 文件")
        print(f"目录: {input_dir}")
        sys.exit(2)   # 专用退出码：目录为空
    elif result.all_success:
        print(f"✅ 转写完成: {result.success}/{result.found} 成功")
        sys.exit(0)
    elif result.has_work:
        print(f"⚠️ 转写完成: {result.success}/{result.found} 成功, {result.failed} 失败")
        if result.errors:
            print("失败详情:")
            for e in result.errors:
                print(f"  - {e}")
        sys.exit(1)   # 部分失败
    else:
        print(f"❌ 转写异常")
        sys.exit(3)
