"""
B站公开 API 工具模块
提供不需要 Cookie 的视频元数据查询功能
"""
import requests
from datetime import datetime
from typing import Optional, Dict


def get_video_info_by_bvid(bvid: str) -> Optional[Dict]:
    """
    通过 BVID 获取视频元数据（无需 Cookie，公开 API）
    返回: {title, owner_name, owner_mid, publish_date, duration, category, tags}
    """
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data['code'] != 0:
            print(f"  ⚠️ B站 API 错误: {data.get('message', '未知')}")
            return None

        vdata = data['data']
        pub_date = None
        ctime = vdata.get('ctime', 0)
        if ctime:
            pub_date = datetime.fromtimestamp(ctime).date()

        return {
            'title': vdata.get('title', ''),
            'owner_name': vdata.get('owner', {}).get('name', 'unknown'),
            'owner_mid': str(vdata.get('owner', {}).get('mid', '')),
            'publish_date': pub_date,
            'duration': vdata.get('duration', 0),
            'category': vdata.get('tname', ''),
            'tags': vdata.get('tname', ''),
        }
    except Exception as e:
        print(f"  ⚠️ B站 API 请求失败: {e}")
        return None
