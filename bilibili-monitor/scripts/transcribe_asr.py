#!/usr/bin/env python3
"""
硅基流动云 ASR 转写模块
使用 SenseVoiceSmall 模型（免费）替代本地 Whisper

API 文档：https://api-docs.siliconflow.cn/docs/api/audio-transcriptions-post
端点：POST https://api.siliconflow.cn/v1/audio/transcriptions
模型：FunAudioLLM/SenseVoiceSmall（免费）
限制：文件 ≤ 50MB，时长 ≤ 1小时
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass

import yaml


# ASR API 配置
ASR_API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
ASR_DEFAULT_MODEL = "FunAudioLLM/SenseVoiceSmall"
ASR_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# 用量记录目录
ASR_USAGE_DIR_NAME = ".asr_config"


@dataclass
class TranscribeResult:
    """转写结果"""
    found: int
    success: int
    failed: int
    skipped: int = 0  # 超大小跳过的文件数
    total_duration: float = 0.0  # 总音频时长（秒）
    total_time: float = 0.0  # 总转写耗时（秒）


def _load_asr_config() -> Dict:
    """加载 ASR 设置（从共享卷读取）"""
    # 优先从环境变量读取数据目录
    data_dir = os.getenv("BILIBILI_DATA_DIR", "")
    if not data_dir:
        # 回退到默认路径
        data_dir = str(Path(__file__).parent.parent / "data")

    asr_dir = Path(data_dir) / ASR_USAGE_DIR_NAME
    settings_file = asr_dir / "settings.json"

    if settings_file.exists():
        try:
            with open(settings_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {"enabled": False, "monthly_budget_minutes": 60, "model": ASR_DEFAULT_MODEL}


def _load_asr_usage() -> Dict:
    """加载 ASR 用量（从共享卷读取）"""
    data_dir = os.getenv("BILIBILI_DATA_DIR", "")
    if not data_dir:
        data_dir = str(Path(__file__).parent.parent / "data")

    usage_file = Path(data_dir) / ASR_USAGE_DIR_NAME / "usage.json"

    if usage_file.exists():
        try:
            with open(usage_file, encoding="utf-8") as f:
                usage = json.load(f)
            # 检查月份
            current_month = datetime.now().strftime("%Y-%m")
            if usage.get("month") == current_month:
                return usage
        except Exception:
            pass

    return {
        "month": datetime.now().strftime("%Y-%m"),
        "total_minutes": 0,
        "records": [],
    }


def _save_asr_usage(usage: Dict):
    """保存 ASR 用量"""
    data_dir = os.getenv("BILIBILI_DATA_DIR", "")
    if not data_dir:
        data_dir = str(Path(__file__).parent.parent / "data")

    asr_dir = Path(data_dir) / ASR_USAGE_DIR_NAME
    asr_dir.mkdir(parents=True, exist_ok=True)

    usage_file = asr_dir / "usage.json"
    with open(usage_file, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False, indent=2)


def _add_usage_record(up_name: str, title: str, duration_minutes: float, bvid: str = ""):
    """添加用量记录"""
    usage = _load_asr_usage()

    record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "up_name": up_name,
        "title": title,
        "duration_minutes": duration_minutes,
        "bvid": bvid,
        "cost": 0,  # SenseVoiceSmall 免费
    }

    usage["records"].append(record)
    usage["total_minutes"] += duration_minutes

    _save_asr_usage(usage)


def transcribe_file(
    audio_path: str,
    api_key: str,
    model: str = ASR_DEFAULT_MODEL,
    timeout: int = 120,
) -> str:
    """
    单文件 ASR 转写

    Args:
        audio_path: 音频文件路径
        api_key: SiliconFlow API Key
        model: ASR 模型名称
        timeout: 请求超时（秒）

    Returns:
        转写文本

    Raises:
        Exception: 转写失败
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {audio_path}")

    # 检查文件大小
    file_size = path.stat().st_size
    if file_size > ASR_MAX_FILE_SIZE:
        raise ValueError(f"文件过大: {file_size / 1024 / 1024:.1f}MB > 50MB 限制")

    # 构造请求
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    with open(path, "rb") as f:
        files = {
            "file": (path.name, f),
            "model": (None, model),
        }

        response = requests.post(
            ASR_API_URL,
            headers=headers,
            files=files,
            timeout=timeout,
        )

    if response.status_code != 200:
        error_msg = response.text[:200]
        raise Exception(f"ASR API 错误 (HTTP {response.status_code}): {error_msg}")

    data = response.json()
    text = data.get("text", "")

    if not text:
        raise Exception("ASR 返回空文本")

    return text


def get_audio_duration(audio_path: str) -> float:
    """获取音频时长（秒），使用 ffprobe"""
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        duration = float(result.stdout.strip())
        return duration
    except Exception:
        return 0.0


def extract_bvid(filename: str) -> str:
    """从文件名提取 BVID"""
    import re
    match = re.search(r"(BV[a-zA-Z0-9]+)", filename)
    return match.group(1) if match else ""


def build_existing_index(transcripts_dir: Path) -> set:
    """构建已转写文件的 BVID 索引"""
    existing = set()
    if not transcripts_dir.exists():
        return existing

    for txt_file in transcripts_dir.glob("*.txt"):
        bvid = extract_bvid(txt_file.name)
        if bvid:
            existing.add(bvid)

    return existing


def process_directory_asr(
    m4a_dir: str,
    transcripts_dir: str,
    uid: str,
    up_name: str = "",
    api_key: str = "",
    model: str = ASR_DEFAULT_MODEL,
    min_duration: float = 60.0,
    **kwargs,
) -> TranscribeResult:
    """
    批量 ASR 转写目录下的 m4a 文件

    接口与 transcribe_local.process_directory() 兼容

    Args:
        m4a_dir: m4a 文件目录
        transcripts_dir: 转写输出目录
        uid: UP主 UID
        up_name: UP主名称
        api_key: SiliconFlow API Key
        model: ASR 模型
        min_duration: 最小时长（秒），低于此跳过

    Returns:
        TranscribeResult
    """
    if not api_key:
        api_key = os.getenv("SILICONFLOW_API_KEY", "")
    if not api_key:
        raise ValueError("缺少 SILICONFLOW_API_KEY 环境变量")

    m4a_path = Path(m4a_dir)
    transcripts_path = Path(transcripts_dir)
    transcripts_path.mkdir(parents=True, exist_ok=True)

    # 扫描 m4a 文件
    m4a_files = sorted(m4a_path.glob("*.m4a"))
    if not m4a_files:
        print(f"[ASR] 没有找到 .m4a 文件: {m4a_dir}")
        return TranscribeResult(found=0, success=0, failed=0)

    # 构建已转写索引
    existing = build_existing_index(transcripts_path)

    # 过滤已转写
    to_transcribe = []
    for m4a in m4a_files:
        bvid = extract_bvid(m4a.name)
        if bvid and bvid in existing:
            continue
        to_transcribe.append(m4a)

    print(f"[ASR] 待转写: {len(to_transcribe)} 个（已跳过 {len(m4a_files) - len(to_transcribe)} 个）")

    if not to_transcribe:
        return TranscribeResult(found=len(m4a_files), success=0, failed=0, skipped=len(m4a_files))

    # 检查预算
    asr_config = _load_asr_config()
    budget_minutes = asr_config.get("monthly_budget_minutes", 60)
    usage = _load_asr_usage()
    used_minutes = usage.get("total_minutes", 0)

    if used_minutes >= budget_minutes:
        print(f"[ASR] 月度预算已用完 ({used_minutes:.1f}/{budget_minutes} 分钟)，跳过转写")
        return TranscribeResult(found=len(to_transcribe), success=0, failed=0, skipped=len(to_transcribe))

    # 逐文件转写
    success = 0
    failed = 0
    skipped = 0
    total_duration = 0.0
    total_time = 0.0

    for i, m4a in enumerate(to_transcribe):
        name = m4a.name
        print(f"[ASR] [{i+1}/{len(to_transcribe)}] {name}")

        try:
            # 获取时长
            duration = get_audio_duration(str(m4a))
            if duration < min_duration:
                print(f"  ⏭️ 时长不足 ({duration:.0f}s < {min_duration:.0f}s)，跳过")
                skipped += 1
                continue

            # 检查文件大小
            file_size = m4a.stat().st_size
            if file_size > ASR_MAX_FILE_SIZE:
                print(f"  ⏭️ 文件过大 ({file_size / 1024 / 1024:.1f}MB > 50MB)，跳过")
                skipped += 1
                continue

            # 再次检查预算
            usage = _load_asr_usage()
            used_minutes = usage.get("total_minutes", 0)
            if used_minutes + duration / 60 > budget_minutes:
                print(f"  ⏭️ 预算不足（已用 {used_minutes:.1f} 分钟 + {duration/60:.1f} 分钟 > {budget_minutes} 分钟），跳过")
                skipped += 1
                continue

            # 调用 ASR API
            t1 = time.time()
            text = transcribe_file(str(m4a), api_key, model)
            elapsed = time.time() - t1
            total_time += elapsed
            total_duration += duration

            # 写入文本文件
            bvid = extract_bvid(name)
            title = m4a.stem.rsplit(" [", 1)[0] if " [" in m4a.stem else m4a.stem
            txt_name = f"{title} [{bvid}].txt" if bvid else f"{m4a.stem}.txt"
            txt_path = transcripts_path / txt_name

            txt_path.write_text(text + "\n", encoding="utf-8")

            # 记录用量
            _add_usage_record(up_name, title, duration / 60, bvid)

            rt = elapsed / duration if duration > 0 else 0
            print(f"  ✅ {len(text)} 字 | {elapsed:.1f}s | RTF={rt:.2f}")
            success += 1

        except Exception as e:
            print(f"  ❌ 失败: {e}")
            failed += 1

    summary = f"✅ {success} | ❌ {failed} | ⏭️ {skipped} | 总音频 {int(total_duration)}s | 转写 {total_time:.1f}s"
    print(f"[ASR] {summary}")

    return TranscribeResult(
        found=len(to_transcribe),
        success=success,
        failed=failed,
        skipped=skipped,
        total_duration=total_duration,
        total_time=total_time,
    )


if __name__ == "__main__":
    # 测试
    import sys

    if len(sys.argv) < 3:
        print("用法: python transcribe_asr.py <m4a目录> <输出目录> [UP主名称]")
        sys.exit(1)

    m4a_dir = sys.argv[1]
    transcripts_dir = sys.argv[2]
    up_name = sys.argv[3] if len(sys.argv) > 3 else ""

    result = process_directory_asr(
        m4a_dir=m4a_dir,
        transcripts_dir=transcripts_dir,
        uid="test",
        up_name=up_name,
    )

    print(f"\n结果: {result}")
