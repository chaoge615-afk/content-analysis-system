"""
统一配置加载器
所有子项目共享此模块，从根目录 .env 文件加载 API 配置
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 定位根目录 .env 文件（ai项目/.env）
_CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = _CURRENT_FILE.parent.parent  # 从 shared/ 回到项目根
ENV_FILE = ROOT_DIR / ".env"

# 加载 .env
load_dotenv(ENV_FILE)


class EmbeddingConfig:
    """Embedding API 配置"""
    def __init__(self):
        self.provider = os.getenv("EMBEDDING_PROVIDER", "siliconflow")
        self.api_key = os.getenv("EMBEDDING_API_KEY", "")
        self.base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
        self.model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
        self.model_alt = os.getenv("EMBEDDING_MODEL_ALT", "Qwen/Qwen3-VL-Embedding-8B")

    def is_configured(self) -> bool:
        """检查是否已配置 API Key"""
        return bool(self.api_key)

    def __repr__(self):
        return f"EmbeddingConfig(provider={self.provider}, model={self.model}, configured={self.is_configured()})"


class ChatConfig:
    """Chat API 配置（MiniMax + DeepSeek）"""
    def __init__(self):
        # MiniMax（主 Chat API）
        self.provider = os.getenv("CHAT_PROVIDER", "minimax")
        self.api_key = os.getenv("CHAT_API_KEY", "")
        self.base_url = os.getenv("CHAT_BASE_URL", "https://api.minimaxi.com/anthropic")
        self.model = os.getenv("CHAT_MODEL", "MiniMax-M2.7")
        self.group_id = os.getenv("MINIMAX_GROUP_ID", "")

        # DeepSeek（精炼专用）
        self.refine_url = os.getenv("REFINE_API_URL", "http://10.168.165.50:3300/v1/chat/completions")
        self.refine_key = os.getenv("REFINE_API_KEY", "")
        self.refine_model = os.getenv("REFINE_MODEL", "deepseek-v4-pro")

    def is_configured(self) -> bool:
        """检查主 Chat API 是否已配置"""
        return bool(self.api_key)

    def is_refine_configured(self) -> bool:
        """检查精炼 API 是否已配置"""
        return bool(self.refine_key)

    def __repr__(self):
        return f"ChatConfig(provider={self.provider}, model={self.model}, configured={self.is_configured()})"


class UnifiedConfig:
    """统一配置管理器"""
    def __init__(self):
        self.embedding = EmbeddingConfig()
        self.chat = ChatConfig()

    def validate(self) -> dict:
        """验证所有 API 配置，返回状态报告"""
        return {
            "embedding": {
                "configured": self.embedding.is_configured(),
                "provider": self.embedding.provider,
                "model": self.embedding.model,
            },
            "chat": {
                "configured": self.chat.is_configured(),
                "provider": self.chat.provider,
                "model": self.chat.model,
            },
            "refine": {
                "configured": self.chat.is_refine_configured(),
                "model": self.chat.refine_model,
            },
        }

    def print_status(self):
        """打印配置状态"""
        status = self.validate()
        print("\n=== API Config Status ===")
        for category, info in status.items():
            icon = "[OK]" if info["configured"] else "[  ]"
            print(f"{icon} {category.upper()}: {info.get('provider', 'N/A')} - {info.get('model', 'N/A')}")
        print()


# 全局配置实例
config = UnifiedConfig()


# 兼容性接口（供旧代码使用）
def get_embedding_config() -> EmbeddingConfig:
    """获取 Embedding 配置"""
    return config.embedding


def get_chat_config() -> ChatConfig:
    """获取 Chat 配置"""
    return config.chat


# 向后兼容的环境变量映射
def setup_compat_env():
    """
    设置兼容性环境变量
    让旧代码无需修改即可使用统一配置
    """
    # personal-knowledge-rag 兼容
    if not os.getenv("SILICONFLOW_API_KEY") and config.embedding.api_key:
        os.environ["SILICONFLOW_API_KEY"] = config.embedding.api_key
    if not os.getenv("SILICONFLOW_BASE_URL") and config.embedding.base_url:
        os.environ["SILICONFLOW_BASE_URL"] = config.embedding.base_url

    # text-to-sql 兼容
    if not os.getenv("MINIMAX_API_KEY") and config.chat.api_key:
        os.environ["MINIMAX_API_KEY"] = config.chat.api_key
    if not os.getenv("MINIMAX_BASE_URL") and config.chat.base_url:
        os.environ["MINIMAX_BASE_URL"] = config.chat.base_url

    # bilibili-monitor 兼容
    if not os.getenv("REFINE_API_URL") and config.chat.refine_url:
        os.environ["REFINE_API_URL"] = config.chat.refine_url
    if not os.getenv("REFINE_API_KEY") and config.chat.refine_key:
        os.environ["REFINE_API_KEY"] = config.chat.refine_key
    if not os.getenv("REFINE_MODEL") and config.chat.refine_model:
        os.environ["REFINE_MODEL"] = config.chat.refine_model


# 自动设置兼容性环境变量
setup_compat_env()


if __name__ == "__main__":
    # 测试配置加载
    config.print_status()
    print(f"\n配置文件路径: {ENV_FILE}")
    print(f"配置文件存在: {ENV_FILE.exists()}")
