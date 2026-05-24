"""
Cookie文件解析工具 - 解析Netscape格式cookie
"""
import os
import re
from typing import Dict


def parse_netscape_cookie(cookie_file: str) -> Dict[str, str]:
    """
    解析Netscape格式的cookie文件，返回所需cookie字典
    支持 Tab 或空格分隔，自动去除空白字符
    """
    needed_keys = {'SESSDATA', 'bili_jct', 'buvid3', 'buvid4', 'DedeUserID', 'DedeUserID__ckMd5'}
    cookies = {}

    if not os.path.exists(cookie_file):
        raise FileNotFoundError(f"Cookie文件不存在: {cookie_file}")

    with open(cookie_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue

            # 切分字段：支持 Tab 或连续空格（浏览器导出格式不统一）
            parts = re.split(r'\s+|\\t', line)
            if len(parts) < 7:
                continue

            domain  = parts[0]
            _, path, secure, expiration, name, value = parts[1:7]

            # secure 字段容错：大写 TRUE / 小写 true / 空
            secure_flag = secure.strip().upper()
            if secure_flag not in ('TRUE', 'FALSE', ''):
                # 可能是字段错位，尝试过滤非布尔值
                continue

            if name in needed_keys:
                cookies[name] = value

    # 调试输出
    print(f"  [cookie debug] 解析到 {len(cookies)} 个字段: {set(cookies.keys())}")

    # 检查必需cookie
    required = {'SESSDATA', 'bili_jct', 'DedeUserID'}
    missing = required - set(cookies.keys())
    if missing:
        raise ValueError(f"Cookie文件缺少必需字段: {missing}")

    return cookies


def load_cookie_from_file(cookie_path: str) -> Dict[str, str]:
    """加载cookie，支持~扩展"""
    cookie_path = os.path.expanduser(cookie_path)
    return parse_netscape_cookie(cookie_path)
