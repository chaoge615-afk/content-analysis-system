"""Router Agent 配置"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录 .env（共享配置）
ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

# 加载本服务 .env（覆盖共享配置）
PROJECT_DIR = Path(__file__).parent.parent
load_dotenv(PROJECT_DIR / ".env")

# ============ LLM 配置（MiniMax M2.7，用于意图分类和结果融合）============
CHAT_API_KEY = os.getenv("CHAT_API_KEY", os.getenv("MINIMAX_API_KEY", ""))
# MiniMax OpenAI 兼容端点（/v1），不是 Anthropic 端点（/anthropic）
CHAT_API_URL = os.getenv("CHAT_API_URL", "https://api.minimaxi.com/v1")
CHAT_MODEL = os.getenv("CHAT_MODEL", "MiniMax-M2.7")

# ============ 子系统 API 地址 ============
# Text-to-SQL 服务
SQL_SERVICE_URL = os.getenv("SQL_SERVICE_URL", "http://localhost:8010")
# RAG 服务
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8090")

# ============ 服务配置 ============
PORT = int(os.getenv("ROUTER_PORT", "8000"))
HOST = os.getenv("ROUTER_HOST", "0.0.0.0")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
