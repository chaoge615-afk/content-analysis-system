# 统一 API 配置使用指南

## 概述

所有子项目共享根目录的 `.env` 文件，按功能分为 **Embedding** 和 **Chat** 两类 API。

## 配置结构

```
ai项目/
├── .env                    # 统一配置文件（不提交到 git）
├── .env.example            # 配置模板
└── shared/shared_config.py        # 统一配置加载器
```

## API 分类

### 1. Embedding API（文本向量化）

**用途**：语义检索、知识库构建、相似度计算

**提供商**：SiliconFlow（硅基流动）

**配置项**：
```bash
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

**使用项目**：
- personal-knowledge-rag
- bilibili-monitor（ChromaDB 写入）
- relationship-analysis

### 2. Chat API（智能对话）

**用途**：内容精炼、问答生成、意图分类、SQL 生成

#### 2.1 MiniMax M2.7（主 Chat API）

**提供商**：MiniMax（同时兼容 Anthropic SDK 和 OpenAI SDK）

> 本项目使用 Anthropic 兼容接口（`/anthropic`），但 MiniMax 也提供 OpenAI 兼容端点（`https://api.minimaxi.com/v1`），可按需切换。

**配置项**：
```bash
CHAT_PROVIDER=minimax
CHAT_API_KEY=eyJxxx
CHAT_BASE_URL=https://api.minimaxi.com/anthropic
CHAT_MODEL=MiniMax-M2.7
MINIMAX_GROUP_ID=0
```

**使用项目**：
- text-to-sql（SQL 生成）
- router-agent（意图分类）
- personal-knowledge-rag（问答备选）

#### 2.2 DeepSeek（精炼 + RAG 问答）

**提供商**：DeepSeek 官方 API

**配置项**：
```bash
REFINE_API_URL=https://api.deepseek.com/v1/chat/completions
REFINE_API_KEY=sk-xxx
REFINE_MODEL=deepseek-v4-flash
```

> 所有子项目统一从 `.env` 读取 `REFINE_*` 变量，**代码中无硬编码默认值**。切换 API 只需改 `.env`，无需改代码。

**使用项目**：
- bilibili-monitor（refiner_domains.py 内容精炼）
- personal-knowledge-rag（RAG 问答默认 LLM）
- relationship-analysis/scripts/refine_batch.py（批量精炼）

## 在子项目中使用

### 方式 1：直接导入 shared_config（推荐）

```python
import sys
from pathlib import Path

# 添加根目录到路径
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared_config import config

# 使用 Embedding 配置
embedding_api_key = config.embedding.api_key
embedding_base_url = config.embedding.base_url
embedding_model = config.embedding.model

# 使用 Chat 配置
chat_api_key = config.chat.api_key
chat_base_url = config.chat.base_url
chat_model = config.chat.model

# 使用 Refine 配置
refine_url = config.chat.refine_url
refine_key = config.chat.refine_key
```

### 方式 2：使用兼容性环境变量

`shared/shared_config.py` 会自动设置以下兼容性环境变量，旧代码无需修改：

```python
# 自动映射
SILICONFLOW_API_KEY ← EMBEDDING_API_KEY
SILICONFLOW_BASE_URL ← EMBEDDING_BASE_URL
MINIMAX_API_KEY ← CHAT_API_KEY
MINIMAX_BASE_URL ← CHAT_BASE_URL
REFINE_API_URL ← REFINE_API_URL
REFINE_API_KEY ← REFINE_API_KEY
REFINE_MODEL ← REFINE_MODEL
```

只需在代码开头导入：

```python
from shared_config import config  # 自动设置兼容环境变量

# 然后正常使用旧的环境变量名
import os
api_key = os.getenv("SILICONFLOW_API_KEY")  # 自动从 EMBEDDING_API_KEY 映射
```

### 方式 3：检查配置状态

```python
from shared_config import config

# 打印配置状态
config.print_status()

# 或获取详细状态
status = config.validate()
print(status)
# {
#     "embedding": {"configured": True, "provider": "siliconflow", "model": "BAAI/bge-large-zh-v1.5"},
#     "chat": {"configured": True, "provider": "minimax", "model": "MiniMax-M2.7"},
#     "refine": {"configured": True, "model": "deepseek-v4-flash"}
# }
```

## 项目集成示例

### bilibili-monitor

```python
# src/refiner.py
from shared_config import config

API_URL = config.chat.refine_url
API_KEY = config.chat.refine_key
REFINE_MODEL = config.chat.refine_model
```

### personal-knowledge-rag

```python
# rag_engine.py
from shared_config import config

class SiliconFlowEmbeddings(Embeddings):
    def __init__(self):
        self.api_key = config.embedding.api_key
        self.base_url = config.embedding.base_url
        self.model = config.embedding.model
```

### text-to-sql

```python
# src/config.py
from shared_config import config

MINIMAX_API_KEY = config.chat.api_key
MINIMAX_BASE_URL = config.chat.base_url
MODEL_NAME = config.chat.model
```

## API 申请

- **SiliconFlow**：https://siliconflow.cn/
  - 注册送积分，Embedding 模型免费额度充足
  - 推荐模型：BAAI/bge-large-zh-v1.5（中文优化）

- **MiniMax**：https://www.minimaxi.com/
  - M2.7 模型，同时兼容 Anthropic SDK 和 OpenAI SDK
  - 本项目使用 Anthropic 兼容接口，适合复杂推理和代码生成

- **DeepSeek**：https://platform.deepseek.com
  - 推荐模型：`deepseek-v4-flash`（精炼，快且便宜）、`deepseek-v4-pro`（复杂推理）
  - OpenAI 兼容接口，也是 RAG 问答默认 LLM
  - 注意：`deepseek-chat` / `deepseek-reasoner` 将于 2026/07/24 弃用

## 常见问题

### Q: 为什么不直接在各项目中配置 .env？

A: 统一配置的优势：
1. **一处配置，多处使用**：避免在 4 个项目中重复填写相同的 API Key
2. **集中管理**：所有 API 密钥在一个文件中，便于备份和轮换
3. **向后兼容**：自动设置旧环境变量名，现有代码无需修改
4. **分类清晰**：按功能（Embedding/Chat）分组，而非按项目

### Q: 如果某个项目需要特殊的 API 配置怎么办？

A: 可以在项目自己的 `.env` 中覆盖：

```python
# 项目级 .env（优先级高于根目录）
CHAT_MODEL=custom-model
```

```python
# 代码中手动覆盖
from shared_config import config
import os

# 项目级配置优先
model = os.getenv("CHAT_MODEL", config.chat.model)
```

### Q: 如何测试配置是否正确？

A: 运行配置检查：

```bash
cd ai项目
python shared/shared_config.py
```

输出示例：
```
=== API Config Status ===
[OK] EMBEDDING: siliconflow - BAAI/bge-large-zh-v1.5
[OK] CHAT: minimax - MiniMax-M2.7
[OK] REFINE: N/A - deepseek-v4-flash
```

## 更新日志

- **2026-06-03**：REFINE 配置集中化，去掉所有 `.py` 文件中的硬编码默认值，统一从 `.env` 读取；DeepSeek 切换为官方 API（`api.deepseek.com`），默认模型改为 `deepseek-v4-flash`
- **2026-05-25**：修正 DeepSeek 端点（10.168.165.50:3300），添加 RAG 作为 DeepSeek 用户，MinimaxEmbeddings → SiliconFlowEmbeddings，MiniMax 用户新增 router-agent
- **2026-05-24**：初始版本，统一 Embedding 和 Chat 配置
- 支持项目：bilibili-monitor, personal-knowledge-rag, text-to-sql, router-agent, relationship-analysis
