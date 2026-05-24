"""Configuration management for Text-to-SQL Multi-Agent System."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_current_file = Path(__file__).resolve()
PROJECT_ROOT = _current_file.parent.parent
_env_file = PROJECT_ROOT / ".env"
load_dotenv(_env_file)

# Database Configuration
# 共享 bilibili-monitor 的 content.db（包含营养数据 + 视频数据）
_default_db = PROJECT_ROOT.parent / "bilibili-monitor" / "data" / "content.db"
DATABASE_PATH = os.getenv("DATABASE_PATH", str(_default_db))

# MiniMax API Configuration
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic")
MODEL_NAME = os.getenv("MODEL_NAME", "MiniMax-M2.7")

# Agent Configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
