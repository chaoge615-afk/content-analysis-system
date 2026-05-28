"""
QQ 机器人通知模块
获取 Access Token 并发送 C2C 消息
"""
import os
import base64
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# 加载项目 .env 文件
load_dotenv()


def _load_qq_creds() -> tuple:
    """从环境变量读取 QQ 凭证"""
    app_id = os.getenv("QQ_APP_ID", "")
    client_secret = os.getenv("QQ_CLIENT_SECRET", "")
    if not app_id or not client_secret:
        raise ValueError("未设置 QQ_APP_ID 或 QQ_CLIENT_SECRET 环境变量")
    return app_id, client_secret


def get_access_token() -> str:
    """获取 QQ 机器人 Access Token"""
    app_id, client_secret = _load_qq_creds()
    r = requests.post(
        "https://bots.qq.com/app/getAppAccessToken",
        json={"appId": app_id, "clientSecret": client_secret},
        timeout=15
    )
    r.raise_for_status()
    return r.json()["access_token"]


def send_file(user_openid: str, file_path: str, caption: str = "", token: str = None) -> dict:
    """
    发送文件到 QQ 用户
    user_openid: 用户的 openid
    file_path: 本地文件路径
    caption: 附言
    token: 可选，已有 token 则跳过获取
    返回: API 响应字典
    """
    if token is None:
        token = get_access_token()

    with open(file_path, "rb") as f:
        file_data = base64.b64encode(f.read()).decode()

    headers = {
        "Authorization": f"QQBot {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "file_type": 4,  # MEDIA_TYPE_FILE
        "srv_send_msg": False,
        "file_data": file_data,
        "file_name": os.path.basename(file_path)
    }

    r = requests.post(
        f"https://api.sgroup.qq.com/v2/users/{user_openid}/files",
        headers=headers, json=payload, timeout=120
    )
    r.raise_for_status()
    file_info = r.json().get("file_info")

    # 发送消息（带文件）
    msg_payload = {
        "content": caption,
        "msg_type": 7,  # MSG_TYPE_MEDIA
        "media": {"file_info": file_info},
        "msg_seq": 1
    }
    r2 = requests.post(
        f"https://api.sgroup.qq.com/v2/users/{user_openid}/messages",
        headers=headers, json=msg_payload, timeout=15
    )
    r2.raise_for_status()
    return r2.json()


def send_text(user_openid: str, message: str, token: str = None) -> dict:
    """
    发送纯文本消息到 QQ 用户
    user_openid: 用户的 openid
    message: 消息内容
    token: 可选，已有 token 则跳过获取
    """
    if token is None:
        token = get_access_token()

    headers = {
        "Authorization": f"QQBot {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "content": message,
        "msg_type": 0,  # MSG_TYPE_TEXT
        "msg_seq": 1
    }
    r = requests.post(
        f"https://api.sgroup.qq.com/v2/users/{user_openid}/messages",
        headers=headers, json=payload, timeout=15
    )
    r.raise_for_status()
    return r.json()
