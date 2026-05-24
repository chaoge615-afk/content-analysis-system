"""
下载B站视频（音频）
使用yt-dlp，需要cookie文件来应对需要登录的操作
"""
import os
import subprocess
import sys
from typing import List, Optional


def download_video(url: str, output_dir: str, cookie_file: str, timeout: int = 600) -> Optional[str]:
    """
    下载单个视频（只下载音频）
    返回: 下载的文件路径，失败返回None
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 使用bilibili-transcribe的venv中的yt-dlp
    venv_python = '/home/chaoge/.hermes/skills/bilibili-transcribe/.venv-bilibili-transcribe/bin/python'
    
    cmd = [
        venv_python, '-m', 'yt_dlp',
        '-o', f'{output_dir}/%(title)s [%(id)s].%(ext)s',
        '--extract-audio',
        '--audio-format', 'm4a',
        '--audio-quality', '0',
        '--cookies', cookie_file,
        '--no-playlist',
        '--no-color',
        '--newline',
        url
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return output_dir
        else:
            print(f"下载失败: {result.stderr[-500:]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"下载超时: {url}")
        return None
    except Exception as e:
        print(f"下载异常: {e}")
        return None


def download_videos(urls: List[str], output_dir: str, cookie_file: str, delay: int = 3) -> List[str]:
    """
    批量下载视频
    返回: 成功下载的URL列表
    """
    os.makedirs(output_dir, exist_ok=True)
    succeeded = []
    
    for url in urls:
        print(f"\n开始下载: {url}")
        result = download_video(url, output_dir, cookie_file)
        if result:
            succeeded.append(url)
            print(f"✓ 下载成功")
        else:
            print(f"✗ 下载失败")
        
        # 间隔时间，避免请求过快
        if delay > 0 and url != urls[-1]:
            import time
            time.sleep(delay)
    
    return succeeded
