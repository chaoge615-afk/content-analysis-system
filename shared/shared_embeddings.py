"""
共享 SiliconFlow Embeddings 模块
所有子项目使用统一的 Embedding 实现，避免重复代码

支持项目：bilibili-monitor, personal-knowledge-rag
用法：
    from shared_embeddings import SiliconFlowEmbeddings
    embeddings = SiliconFlowEmbeddings()  # 自动从 .env 读取配置
"""
import os
import sys
from pathlib import Path
from typing import List

# 尝试导入 langchain Embeddings 基类（personal-knowledge-rag 需要，bilibili-monitor 可选）
try:
    from langchain_core.embeddings import Embeddings as _EmbeddingsBase
except ImportError:
    class _EmbeddingsBase:
        """langchain_core 不可用时的空基类"""
        pass

# 加载共享配置
_CURRENT_FILE = Path(__file__).resolve()
_ROOT_DIR = _CURRENT_FILE.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
from shared_config import config as _shared_config


class SiliconFlowEmbeddings(_EmbeddingsBase):
    """
    SiliconFlow Embedding 统一实现（BAAI/bge-large-zh-v1.5）

    支持两种初始化方式：
    1. 自动从 .env 读取配置（推荐）
    2. 显式传入 api_key, model, base_url
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        batch_size: int = 10,
    ):
        # 优先使用显式参数，否则从共享配置读取
        self.api_key = api_key or _shared_config.embedding.api_key
        self.model = model or _shared_config.embedding.model
        self.base_url = base_url or _shared_config.embedding.base_url
        self.batch_size = batch_size

        if not self.api_key:
            raise ValueError(
                "SiliconFlow API key not configured. "
                "Please set EMBEDDING_API_KEY in .env"
            )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量 embed 文档（自动分批处理）"""
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/embeddings"

        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            data = {"input": batch, "model": self.model}

            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            if "data" not in result:
                raise ValueError(f"Unexpected response format: {result}")

            batch_embeddings = [item["embedding"] for item in result["data"]]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """embed 单个查询"""
        vectors = self.embed_documents([text])
        if not vectors or vectors[0] is None:
            raise ValueError("Embedding returned empty or None")
        return vectors[0]
