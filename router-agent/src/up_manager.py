"""
UP主管理模块
支持通过 B站链接自动识别 UP主信息并添加到监控列表
"""

import os
import re
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, List
import requests


# B站链接正则
SPACE_PATTERN = re.compile(r"space\.bilibili\.com/(\d+)")
VIDEO_PATTERN = re.compile(r"bilibili\.com/video/(BV[a-zA-Z0-9]+)")

# 默认 YAML 配置模板
DEFAULT_CONFIG = {
    "cookie_file": "~/.bilibili/cookie.txt",
    "download_root": "~/B站监控",
    "whisper_model": "small",
    "whisper_device": "cpu",  # NAS 用云 ASR，不需要本地 GPU
    "transcribe_output_dir": "",
    "notify_target": "",
    "domain": "emotional",
}

# B站 API 配置
BILIBILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/",
}


class UpManager:
    """UP主管理器：解析链接 → 获取信息 → 创建配置"""

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化 UP主管理器

        Args:
            config_dir: UP主配置文件目录，默认从环境变量或默认路径读取
        """
        if config_dir is None:
            config_dir = os.getenv(
                "BILIBILI_CONFIG_DIR",
                str(Path(__file__).parent.parent.parent / "bilibili-monitor" / "config"),
            )
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def parse_url(self, url: str) -> Dict:
        """
        解析 B站链接，提取标识符

        Args:
            url: B站主页或视频链接

        Returns:
            {
                "type": "space" | "video" | "invalid",
                "identifier": "UID" | "BVID" | None,
                "url": "原始链接"
            }
        """
        url = url.strip()

        # 尝试匹配主页链接
        match = SPACE_PATTERN.search(url)
        if match:
            return {
                "type": "space",
                "identifier": match.group(1),
                "url": url,
            }

        # 尝试匹配视频链接
        match = VIDEO_PATTERN.search(url)
        if match:
            return {
                "type": "video",
                "identifier": match.group(1),
                "url": url,
            }

        return {
            "type": "invalid",
            "identifier": None,
            "url": url,
        }

    def fetch_profile(self, parsed: Dict) -> Dict:
        """
        调 B站 API 获取 UP主信息

        Args:
            parsed: parse_url() 的返回值

        Returns:
            {
                "success": True/False,
                "uid": "数字UID",
                "name": "UP主名称",
                "face": "头像URL",
                "error": "错误信息" (if failed)
            }
        """
        if parsed["type"] == "invalid":
            return {"success": False, "error": "无效的链接格式"}

        try:
            if parsed["type"] == "video":
                # 视频链接 → 获取视频信息 → 提取 UP主 UID
                return self._fetch_from_video(parsed["identifier"])
            else:
                # 主页链接 → 直接获取 UP主信息
                return self._fetch_from_space(parsed["identifier"])

        except requests.exceptions.Timeout:
            return {"success": False, "error": "B站 API 请求超时"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"网络请求失败: {e}"}
        except Exception as e:
            return {"success": False, "error": f"未知错误: {e}"}

    def _fetch_from_video(self, bvid: str) -> Dict:
        """从视频链接获取 UP主信息"""
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        resp = requests.get(url, headers=BILIBILI_HEADERS, timeout=10)
        data = resp.json()

        if data.get("code") != 0:
            return {
                "success": False,
                "error": f"B站 API 错误: {data.get('message', '未知')}",
            }

        video_data = data.get("data", {})
        owner = video_data.get("owner", {})

        return {
            "success": True,
            "uid": str(owner.get("mid", "")),
            "name": owner.get("name", "未知"),
            "face": owner.get("face", ""),
            "video_title": video_data.get("title", ""),  # 附加：视频标题
        }

    def _fetch_from_space(self, uid: str) -> Dict:
        """从主页链接获取 UP主信息"""
        # 使用公开 API 获取基本信息（不需要 WBI 签名）
        url = f"https://api.bilibili.com/x/space/wbi/acc/info?mid={uid}"
        resp = requests.get(url, headers=BILIBILI_HEADERS, timeout=10)
        data = resp.json()

        if data.get("code") != 0:
            # 降级：尝试另一个 API
            return self._fetch_from_space_fallback(uid)

        space_data = data.get("data", {})

        return {
            "success": True,
            "uid": uid,
            "name": space_data.get("name", "未知"),
            "face": space_data.get("face", ""),
        }

    def _fetch_from_space_fallback(self, uid: str) -> Dict:
        """备用方法：通过视频列表获取 UP主名称"""
        # 获取 UP主最近视频，从视频信息中提取名称
        url = f"https://api.bilibili.com/x/space/arc/search?mid={uid}&ps=1"
        resp = requests.get(url, headers=BILIBILI_HEADERS, timeout=10)
        data = resp.json()

        if data.get("code") != 0:
            return {
                "success": False,
                "error": f"无法获取 UP主信息 (UID: {uid})",
            }

        vlist = data.get("data", {}).get("list", {}).get("vlist", [])
        if vlist:
            return {
                "success": True,
                "uid": uid,
                "name": vlist[0].get("author", "未知"),
                "face": "",
            }

        return {
            "success": False,
            "error": f"UP主无视频或无法获取信息 (UID: {uid})",
        }

    def add_up(self, url: str, whisper_model: str = "small", domain: str = "emotional") -> Dict:
        """
        添加新 UP主：解析链接 → 获取信息 → 创建 YAML 配置

        Args:
            url: B站链接
            whisper_model: Whisper 模型大小 (tiny/base/small/medium)
            domain: 内容域 (emotional/career)

        Returns:
            {
                "success": True/False,
                "up_info": { uid, name, face, config_file },
                "error": "错误信息"
            }
        """
        # 1. 解析链接
        parsed = self.parse_url(url)
        if parsed["type"] == "invalid":
            return {"success": False, "error": "无效的链接格式"}

        # 2. 获取 UP主信息
        profile = self.fetch_profile(parsed)
        if not profile["success"]:
            return {"success": False, "error": profile["error"]}

        uid = profile["uid"]
        name = profile["name"]

        # 3. 检查是否已存在（按 UID 遍历查找，避免名称不同导致重复）
        existing = None
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                if str(cfg.get("uid", "")) == uid:
                    existing = yaml_file
                    break
            except Exception:
                continue

        if existing:
            return {
                "success": False,
                "error": f"UP主已存在: {name} (UID: {uid})，配置文件: {existing.name}",
            }

        # 4. 生成 YAML 配置（使用名称作为文件名，更易读）
        # 文件名安全处理：替换不适合文件系统的字符
        safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
        config_path = self.config_dir / f"{safe_name}.yaml"
        config = {
            **DEFAULT_CONFIG,
            "name": name,
            "uid": uid,
            "whisper_model": whisper_model,
            "domain": domain,
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            return {
                "success": True,
                "up_info": {
                    "uid": uid,
                    "name": name,
                    "face": profile.get("face", ""),
                    "config_file": config_path.name,
                    "whisper_model": whisper_model,
                    "domain": domain,
                },
            }

        except Exception as e:
            return {"success": False, "error": f"写入配置文件失败: {e}"}

    def list_ups(self) -> List[Dict]:
        """
        列出所有已配置的 UP主

        Returns:
            [
                {
                    "uid": "...",
                    "name": "...",
                    "whisper_model": "...",
                    "config_file": "xxx.yaml",
                    "has_video": True/False (DuckDB 中是否有视频)
                }
            ]
        """
        ups = []

        for yaml_file in sorted(self.config_dir.glob("*.yaml")):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)

                ups.append({
                    "uid": str(cfg.get("uid", "")),
                    "name": cfg.get("name", yaml_file.stem),
                    "whisper_model": cfg.get("whisper_model", "small"),
                    "domain": cfg.get("domain", "emotional"),
                    "config_file": yaml_file.name,
                    "has_video": False,  # 前端可查询 DuckDB 补充
                })
            except Exception:
                # 配置文件损坏时跳过
                continue

        return ups

    def remove_up(self, uid: str) -> Dict:
        """
        删除 UP主配置

        Args:
            uid: UP主 UID

        Returns:
            {"success": True/False, "message": "...", "error": "..."}
        """
        # 查找配置文件
        config_path = self.config_dir / f"{uid}.yaml"

        if not config_path.exists():
            # 尝试从其他文件名中查找
            for yaml_file in self.config_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, encoding="utf-8") as f:
                        cfg = yaml.safe_load(f)
                    if str(cfg.get("uid", "")) == uid:
                        config_path = yaml_file
                        break
                except Exception:
                    continue

        if not config_path.exists():
            return {"success": False, "error": f"未找到 UID {uid} 的配置文件"}

        try:
            # 读取名称用于提示
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            name = cfg.get("name", "未知")

            # 删除文件
            config_path.unlink()

            return {
                "success": True,
                "message": f"已删除 UP主: {name} (UID: {uid})",
            }

        except Exception as e:
            return {"success": False, "error": f"删除失败: {e}"}
