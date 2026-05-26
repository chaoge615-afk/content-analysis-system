"""
ASR 设置和用量管理模块
支持预算上限 + 手动开关控制成本
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List


class AsrManager:
    """ASR 设置和用量管理器"""

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化 ASR 管理器

        Args:
            data_dir: 数据存储目录，默认从环境变量读取
        """
        if data_dir is None:
            data_dir = os.getenv(
                "BILIBILI_DATA_DIR",
                str(Path(__file__).parent.parent.parent / "bilibili-monitor" / "data"),
            )
        self.data_dir = Path(data_dir)
        self.asr_dir = self.data_dir / ".asr_config"
        self.asr_dir.mkdir(parents=True, exist_ok=True)

        self.settings_file = self.asr_dir / "settings.json"
        self.usage_file = self.asr_dir / "usage.json"

        # 初始化默认设置
        self._ensure_settings_file()

    def _ensure_settings_file(self):
        """确保设置文件存在"""
        if not self.settings_file.exists():
            default_settings = {
                "enabled": False,
                "monthly_budget_minutes": 60,
                "model": "FunAudioLLM/SenseVoiceSmall",
                "created_at": datetime.now().isoformat(),
            }
            self._write_json(self.settings_file, default_settings)

    def _read_json(self, path: Path) -> Dict:
        """读取 JSON 文件"""
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_json(self, path: Path, data: Dict):
        """写入 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_settings(self) -> Dict:
        """
        获取 ASR 设置

        Returns:
            {
                "enabled": True/False,
                "monthly_budget_minutes": 60,
                "model": "FunAudioLLM/SenseVoiceSmall"
            }
        """
        settings = self._read_json(self.settings_file)
        return {
            "enabled": settings.get("enabled", False),
            "monthly_budget_minutes": settings.get("monthly_budget_minutes", 60),
            "model": settings.get("model", "FunAudioLLM/SenseVoiceSmall"),
        }

    def update_settings(self, data: Dict) -> Dict:
        """
        更新 ASR 设置

        Args:
            data: 更新的字段 { enabled?, monthly_budget_minutes?, model? }

        Returns:
            更新后的完整设置
        """
        settings = self._read_json(self.settings_file)

        # 合并更新
        if "enabled" in data:
            settings["enabled"] = bool(data["enabled"])
        if "monthly_budget_minutes" in data:
            settings["monthly_budget_minutes"] = float(data["monthly_budget_minutes"])
        if "model" in data:
            settings["model"] = data["model"]

        settings["updated_at"] = datetime.now().isoformat()

        self._write_json(self.settings_file, settings)
        return self.get_settings()

    def get_usage(self) -> Dict:
        """
        获取 ASR 用量

        Returns:
            {
                "month": "2026-05",
                "total_minutes": 23.5,
                "records": [
                    {
                        "date": "2026-05-27",
                        "up_name": "桃姐",
                        "title": "视频标题",
                        "duration_minutes": 8.2,
                        "cost": 0  (SenseVoiceSmall 免费)
                    }
                ]
            }
        """
        usage = self._read_json(self.usage_file)
        current_month = datetime.now().strftime("%Y-%m")

        # 如果月份不匹配，重置
        if usage.get("month") != current_month:
            usage = {
                "month": current_month,
                "total_minutes": 0,
                "records": [],
            }
            self._write_json(self.usage_file, usage)

        return usage

    def add_usage_record(self, record: Dict) -> Dict:
        """
        添加用量记录

        Args:
            record: {
                "up_name": "UP主名称",
                "title": "视频标题",
                "duration_minutes": 8.2,
                "bvid": "BVxxx"  (可选)
            }

        Returns:
            更新后的用量统计
        """
        usage = self.get_usage()  # 确保月份正确

        # 添加记录
        record["date"] = datetime.now().strftime("%Y-%m-%d")
        record["timestamp"] = datetime.now().isoformat()
        record["cost"] = 0  # SenseVoiceSmall 免费

        usage["records"].append(record)
        usage["total_minutes"] += record.get("duration_minutes", 0)

        self._write_json(self.usage_file, usage)
        return usage

    def check_budget(self) -> Dict:
        """
        检查预算是否充足

        Returns:
            {
                "ok": True/False,
                "used_minutes": 23.5,
                "budget_minutes": 60,
                "remaining_minutes": 36.5,
                "message": "预算剩余 36.5 分钟"
            }
        """
        settings = self.get_settings()
        usage = self.get_usage()

        used = usage.get("total_minutes", 0)
        budget = settings.get("monthly_budget_minutes", 60)
        remaining = max(0, budget - used)

        if not settings.get("enabled", False):
            return {
                "ok": False,
                "used_minutes": used,
                "budget_minutes": budget,
                "remaining_minutes": remaining,
                "message": "ASR 已关闭",
            }

        if used >= budget:
            return {
                "ok": False,
                "used_minutes": used,
                "budget_minutes": budget,
                "remaining_minutes": 0,
                "message": f"月度预算已用完 ({used:.1f}/{budget} 分钟)",
            }

        return {
            "ok": True,
            "used_minutes": used,
            "budget_minutes": budget,
            "remaining_minutes": remaining,
            "message": f"预算剩余 {remaining:.1f} 分钟",
        }

    def get_status(self) -> Dict:
        """
        获取 ASR 完整状态（设置 + 用量）

        Returns:
            {
                "settings": {...},
                "usage": {...},
                "budget": {...}
            }
        """
        return {
            "settings": self.get_settings(),
            "usage": self.get_usage(),
            "budget": self.check_budget(),
        }
