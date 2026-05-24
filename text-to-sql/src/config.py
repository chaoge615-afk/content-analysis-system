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
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/nutrition.db")

# MiniMax API Configuration
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic")
MODEL_NAME = os.getenv("MODEL_NAME", "MiniMax-M2.7")

# Agent Configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
