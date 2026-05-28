"""
下载B站视频（音频）
使用yt-dlp，需要cookie文件来应对需要登录的操作
"""
import os
import time
from typing import List, Optional

import yt_dlp


def download_video(url: str, output_dir: str, cookie_file: str, timeout: int = 600) -> Optional[str]:
    """
    下载单个视频（只下载音频）
    返回: 下载的文件路径，失败返回None
    """
    os.makedirs(output_dir, exist_ok=True)

    # yt-dlp 配置
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(title)s [%(id)s].%(ext)s',
        'extractaudio': True,
        'audioformat': 'm4a',
        'audioquality': '0',
        'cookiefile': cookie_file,
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'socket_timeout': timeout,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)
                # 提取音频后会变成 .m4a
                base = os.path.splitext(filename)[0]
                audio_file = base + '.m4a'
                if os.path.exists(audio_file):
                    return audio_file
                # 如果 .m4a 不存在，返回原文件名
                return filename if os.path.exists(filename) else None
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
