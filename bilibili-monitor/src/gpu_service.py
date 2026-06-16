#!/usr/bin/env python3
"""
GPU 转录服务 — 在开发机 (RTX 4060) 上运行的轻量 FastAPI 服务

提供 GPU 检测和转录触发功能，供前端 AdminPanel 调用。
启动方式：
    python gpu_service.py --port 8011

端点：
    GET  /api/gpu/status     — GPU 状态检测（CUDA 可用性、显卡型号）
    POST /api/gpu/transcribe  — 触发 GPU 转录
    GET  /api/gpu/status     — 获取转录任务状态
"""
import argparse
import os
import sys
import io
import threading
import time
from datetime import datetime
from pathlib import Path

# Windows 终端 GBK 编码兼容：强制 stdout 使用 UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Windows: 确保 cublas64_12.dll 在 CTranslate2 包目录（CT2 只搜索自身目录）
_dll_dir_handle = None
if sys.platform == "win32":
    try:
        import nvidia.cublas
        import ctranslate2
        _cublas_bin = Path(nvidia.cublas.__path__[0]) / "bin"
        _ct2_dir = Path(ctranslate2.__path__[0])
        if _cublas_bin.is_dir() and _ct2_dir.is_dir():
            for dll in _cublas_bin.glob("cublas*.dll"):
                target = _ct2_dir / dll.name
                if not target.exists():
                    import shutil
                    shutil.copy2(dll, target)
            _dll_dir_handle = os.add_dll_directory(str(_cublas_bin))
    except Exception:
        pass

# 确保 bilibili-monitor 目录可导入
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="GPU Transcribe Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ GPU 检测 ============

def check_gpu() -> dict:
    """检测 CUDA GPU 状态（使用 CTranslate2，无需 PyTorch）"""
    result = {
        "cuda_available": False,
        "gpu_name": None,
        "gpu_memory_mb": None,
        "torch_version": None,
        "error": None,
    }
    try:
        import ctranslate2
        result["torch_version"] = f"ctranslate2 {ctranslate2.__version__}"
        # CTranslate2 支持列表
        supported_compute = ctranslate2.get_supported_compute_types("cuda")
        if supported_compute:
            result["cuda_available"] = True
            result["gpu_name"] = "NVIDIA GPU (CUDA via CTranslate2)"
            # 尝试用 nvidia-smi 获取显卡名和显存
            try:
                import subprocess
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                    timeout=5, text=True, errors="replace",
                )
                parts = out.strip().split(",")
                if len(parts) >= 2:
                    result["gpu_name"] = parts[0].strip()
                    mem_str = parts[1].strip().replace(" MiB", "")
                    result["gpu_memory_mb"] = int(mem_str)
            except Exception:
                pass  # nvidia-smi 不可用时跳过
        else:
            result["error"] = "CUDA 不可用（CTranslate2 未检测到 CUDA 支持）"
    except ImportError:
        result["error"] = "未安装 CTranslate2（GPU 服务需要 ctranslate2 + faster-whisper）"
    except Exception as e:
        result["error"] = f"GPU 检测异常: {e}"
    return result


# ============ 转录任务管理 ============

class TranscribeTask:
    def __init__(self):
        self._lock = threading.Lock()
        self._task: dict | None = None

    @property
    def status(self) -> dict:
        with self._lock:
            if self._task is None:
                return {"status": "idle", "message": "无任务"}
            return dict(self._task)

    def run(self, downloads: str, transcripts: str, model_size: str = "small", device: str = "cuda"):
        """在新线程中执行转录"""
        with self._lock:
            if self._task and self._task.get("status") == "running":
                return {"success": False, "error": "已有转录任务正在运行"}
            self._task = {
                "status": "running",
                "message": "转录任务启动中...",
                "started_at": datetime.now().isoformat(),
                "downloads": downloads,
                "transcripts": transcripts,
                "model_size": model_size,
                "device": device,
                "logs": [],
                "progress": {"found": 0, "success": 0, "failed": 0, "current": ""},
            }

        thread = threading.Thread(
            target=self._execute,
            args=(downloads, transcripts, model_size, device),
            daemon=True,
        )
        thread.start()
        return {"success": True, "message": "转录任务已启动"}

    def _append_log(self, msg: str):
        with self._lock:
            if self._task and "logs" in self._task:
                self._task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
                if len(self._task["logs"]) > 500:
                    self._task["logs"] = self._task["logs"][-500:]

    def _update_progress(self, **kwargs):
        with self._lock:
            if self._task and "progress" in self._task:
                self._task["progress"].update(kwargs)

    def _execute(self, downloads: str, transcripts: str, model_size: str, device: str):
        start_time = time.time()
        try:
            downloads_dir = Path(downloads).expanduser().resolve()
            transcripts_dir = Path(transcripts).expanduser().resolve()

            # 导入 transcribe_gpu 模块
            from transcribe_gpu import (
                WhisperModel,
                build_existing_index,
                extract_bvid,
                get_audio_duration,
            )

            self._append_log(f"扫描 downloads: {downloads_dir}")
            m4a_files = sorted(downloads_dir.glob("*.m4a"))
            if not m4a_files:
                self._append_log("没有找到 .m4a 文件")
                with self._lock:
                    self._task["status"] = "done"
                    self._task["message"] = "没有需要转写的文件"
                return

            transcripts_dir.mkdir(parents=True, exist_ok=True)
            existing = build_existing_index(transcripts_dir)
            self._append_log(f"已转写: {len(existing)} 个")

            # 过滤
            to_transcribe = []
            for m4a in m4a_files:
                bvid = extract_bvid(m4a.name)
                if bvid and bvid in existing:
                    continue
                to_transcribe.append(m4a)

            self._append_log(f"待转写: {len(to_transcribe)} 个")
            self._update_progress(found=len(to_transcribe))

            if not to_transcribe:
                self._append_log("所有文件均已转写")
                with self._lock:
                    self._task["status"] = "done"
                    self._task["message"] = "所有文件均已转写"
                return

            # 加载模型
            compute_type = "float16" if device == "cuda" else "int8"
            self._append_log(f"加载 Whisper 模型: {model_size} ({device}, {compute_type})")
            self._append_log("(首次运行需下载模型，请耐心等待...)")
            self._update_progress(current=f"加载模型 {model_size}...")
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            self._append_log("模型加载完成")

            success = 0
            failed = 0
            total_audio = 0.0
            total_time = 0.0

            for i, m4a in enumerate(to_transcribe):
                name = m4a.name
                self._append_log(f"[{i+1}/{len(to_transcribe)}] {name}")
                self._update_progress(current=name)

                try:
                    duration = get_audio_duration(m4a)
                    if duration < 1:
                        self._append_log(f"  ⏭️ 无法获取时长，跳过")
                        continue
                    total_audio += duration

                    t1 = time.time()
                    segments, _ = model.transcribe(str(m4a), language="zh")
                    text = "\n".join(
                        (seg.text or "").strip()
                        for seg in segments
                        if (seg.text or "").strip()
                    )
                    elapsed = time.time() - t1
                    total_time += elapsed

                    bvid = extract_bvid(name)
                    title = m4a.stem.rsplit(" [", 1)[0] if " [" in m4a.stem else m4a.stem
                    txt_name = f"{title} [{bvid}].txt" if bvid else f"{m4a.stem}.txt"
                    (transcripts_dir / txt_name).write_text(text + "\n", encoding="utf-8")

                    rt = elapsed / duration if duration > 0 else 0
                    self._append_log(
                        f"  ✅ {len(text)} 字 | {elapsed:.1f}s | RTF={rt:.2f}"
                    )
                    success += 1
                    self._update_progress(success=success)

                except Exception as e:
                    self._append_log(f"  ❌ 失败: {e}")
                    failed += 1
                    self._update_progress(failed=failed)

            elapsed_total = time.time() - start_time
            summary = f"✅ {success} | ❌ {failed} | 总音频 {int(total_audio)}s | 转录 {total_time:.1f}s | 平均RTF {total_time/total_audio:.2f}"
            self._append_log(summary)

            with self._lock:
                self._task["status"] = "done"
                self._task["message"] = summary
                self._task["finished_at"] = datetime.now().isoformat()
                self._task["elapsed"] = round(elapsed_total, 1)

        except Exception as e:
            self._append_log(f"❌ 转录任务异常: {e}")
            with self._lock:
                self._task["status"] = "error"
                self._task["message"] = str(e)


task_manager = TranscribeTask()


# ============ 请求模型 ============

class TranscribeRequest(BaseModel):
    downloads: str  # downloads 目录路径
    transcripts: str  # transcripts 目录路径
    model_size: str = "small"  # 模型大小
    device: str = "cuda"  # 设备: cuda | cpu


# ============ API 端点 ============

@app.get("/api/gpu/check")
async def gpu_check():
    """检测 GPU 状态"""
    gpu_info = check_gpu()
    return {
        "success": True,
        "cuda_available": gpu_info["cuda_available"],
        "gpu_name": gpu_info["gpu_name"],
        "gpu_memory_mb": gpu_info["gpu_memory_mb"],
        "torch_version": gpu_info["torch_version"],
        "error": gpu_info["error"],
    }


@app.post("/api/gpu/transcribe")
async def gpu_transcribe(req: TranscribeRequest):
    """触发 GPU 转录"""
    # 如果请求 cuda 模式，先确认 GPU 可用
    if req.device == "cuda":
        gpu = check_gpu()
        if not gpu["cuda_available"]:
            return {
                "success": False,
                "error": f"GPU 不可用: {gpu.get('error', '未检测到 CUDA')}，请改用 cpu 模式",
            }

    if not req.downloads or not req.transcripts:
        return {
            "success": False,
            "error": "downloads 和 transcripts 目录路径不能为空",
        }

    if not os.path.isdir(req.downloads):
        return {
            "success": False,
            "error": f"downloads 目录不存在: {req.downloads}",
        }

    return task_manager.run(req.downloads, req.transcripts, req.model_size, req.device)


@app.get("/api/gpu/status")
async def gpu_status():
    """获取当前转录任务状态"""
    gpu = check_gpu()
    task = task_manager.status
    return {"success": True, "gpu": gpu, "task": task}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU 转录服务")
    parser.add_argument("--host", default="127.0.0.1", help="绑定地址")
    parser.add_argument("--port", type=int, default=8011, help="端口")
    args = parser.parse_args()

    print(f"GPU 转录服务启动: http://{args.host}:{args.port}")
    print(f"API 文档: http://{args.host}:{args.port}/docs")

    gpu = check_gpu()
    if gpu["cuda_available"]:
        print(f"✅ GPU: {gpu['gpu_name']} ({gpu['gpu_memory_mb']} MB)")
    else:
        print(f"⚠️  {gpu.get('error', 'GPU 不可用')}")

    uvicorn.run(app, host=args.host, port=args.port)