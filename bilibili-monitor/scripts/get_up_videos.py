"""
获取B站UP主最新视频列表
基于WBI签名接口，需要登录态cookie
"""
import requests
import time
import hashlib
import urllib.parse
from functools import reduce

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43,
    5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16,
    24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59,
    6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]


def getMixinKey(orig: str) -> str:
    return reduce(lambda s, i: s + orig[i], MIXIN_KEY_ENC_TAB, '')[:32]


def test_cookie(cookies: dict) -> tuple:
    """
    轻量级 Cookie 有效性检验（调用 /x/web-interface/nav）
    返回 (ok: bool, errmsg: str)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    try:
        resp = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=headers, cookies=cookies, timeout=10)
        resp.raise_for_status()
        json_content = resp.json()
        code = json_content.get('code', 0)
        if code == 0:
            uname = json_content.get('data', {}).get('uname', '')
            return True, uname
        elif code == -352:
            return False, '风控校验失败（Cookie 已过期或被风控）'
        else:
            return False, json_content.get('message', f'code={code}')
    except Exception as e:
        return False, str(e)


def get_wbi_keys(cookies: dict) -> tuple:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    resp = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=headers, cookies=cookies)
    resp.raise_for_status()
    json_content = resp.json()
    img_url = json_content['data']['wbi_img']['img_url']
    sub_url = json_content['data']['wbi_img']['sub_url']
    img_key = img_url.rsplit('/', 1)[1].split('.')[0]
    sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
    return img_key, sub_key


def encWbi(params: dict, img_key: str, sub_key: str) -> dict:
    mixin_key = getMixinKey(img_key + sub_key)
    params['wts'] = round(time.time())
    params = dict(sorted(params.items()))
    params = {
        k: ''.join(filter(lambda c: c not in "!'()*", str(v)))
        for k, v in params.items()
    }
    query = urllib.parse.urlencode(params)
    wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params['w_rid'] = wbi_sign
    return params


def get_up_videos(uid: int, cookies: dict, pn: int = 1, ps: int = 10):
    """获取UP主的视频列表"""
    img_key, sub_key = get_wbi_keys(cookies)

    params = {
        'mid': str(uid),
        'pn': str(pn),
        'ps': str(ps),
        'order': 'pubdate',
        'jsonp': 'jsonp'
    }

    signed_params = encWbi(params, img_key, sub_key)

    url = 'https://api.bilibili.com/x/space/wbi/arc/search'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://space.bilibili.com/{uid}/video',
        'Origin': 'https://www.bilibili.com',
        'Accept': 'application/json, text/plain, */*',
    }

    resp = requests.get(url, params=signed_params, headers=headers, cookies=cookies)
    resp.raise_for_status()
    return resp.json()


def get_video_list(uid: int, cookies: dict, max_count: int = 30) -> list:
    """
    获取UP主最新视频列表（自动翻页）
    返回: [{'bvid': 'BVxxx', 'title': 'xxx', 'created': timestamp, 'aid': ...}, ...]
    """
    all_videos = []
    pn = 1
    ps = 30
    
    while len(all_videos) < max_count:
        result = get_up_videos(uid, cookies, pn=pn, ps=ps)
        
        if result['code'] != 0:
            raise RuntimeError(f"获取视频列表失败: code={result['code']}, message={result.get('message', '未知错误')}")
        
        vlist = result['data']['list']['vlist']
        if not vlist:
            break
            
        all_videos.extend(vlist)
        
        # 如果返回的不够一页，说明到底了
        if len(vlist) < ps:
            break
            
        pn += 1
    
    return all_videos[:max_count]
