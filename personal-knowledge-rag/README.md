# 视频知识库RAG问答系统

B站视频精炼内容的语义检索与问答系统，支持 metadata 过滤 + BM25/向量混合检索。

## 功能特性

- 基于 B站视频精炼内容（三段式摘要）构建知识库
- metadata 过滤检索（按 UP主、分类、BV号等）
- BM25 + 向量混合检索（HybridSearch）
- ChromaDB 向量存储（支持远程/本地两种模式）
- MiniMax M2.7 LLM（Anthropic 兼容接口）
- SiliconFlow Embedding（BAAI/bge-large-zh-v1.5）
- 支持 Web UI、API、命令行三种交互方式
- Docker 部署，纳入统一 docker-compose 编排

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入 API Key:

```
MINIMAX_API_KEY=你的-minimax-api-key
SILICONFLOW_API_KEY=你的-siliconflow-api-key
```

### 3. 添加视频精炼内容

将视频精炼 txt 文件放到 `video_knowledge/` 目录下，支持按分类子目录组织。

文件命名约定: `{bvid}_{title}.txt` 或 `{up_name}_{bvid}_{title}.txt`

### 4. 运行

```bash
# Web UI 方式
python api.py
# 访问 http://localhost:8090

# 命令行方式
python main.py
```

### 5. 加载知识库

**命令行**: 输入 `load`

**CLI脚本**:
```bash
python load_cli.py                    # 加载视频知识库
python load_cli.py --stats            # 查看统计信息
python load_cli.py --clear            # 清空并重新加载
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web UI 页面 |
| `/api/ask_video` | POST | 视频知识库问答（支持 metadata 过滤 + 混合检索） |
| `/api/ask_generic` | POST | 通用问答（可指定 collection） |
| `/api/load_video` | POST | 加载视频知识库 |
| `/api/clear_video` | POST | 清空视频知识库 |
| `/api/stats` | GET | 获取统计信息 |
| `/api/collections` | GET | 获取所有 collection 信息 |
| `/health` | GET | 健康检查 |

### 问答请求示例

```json
POST /api/ask_video
{
    "question": "博主们对冷暴力怎么看？",
    "filters": {"up_name": "桃姐", "category": "01_喜欢"},
    "use_hybrid": true
}
```

## 常用命令（命令行模式）

| 命令 | 作用 |
|------|------|
| `load` | 加载视频精炼内容到知识库 |
| `clear` | 清空视频知识库 |
| `stats` | 查看知识库统计信息 |
| `help` | 显示帮助 |
| `exit` | 退出 |

## 调优参数

在 `.env` 文件中可以调整：

```
CHUNK_SIZE=500        # 分块大小
CHUNK_OVERLAP=50      # 重叠大小
TOP_K=5              # 检索数量
```

## Docker 部署

纳入根目录 `docker-compose.yml` 统一编排：

```bash
# 启动所有服务（含 RAG）
docker compose --profile nas up -d

# 单独重建 RAG 镜像
docker compose --profile nas build rag

# 查看 RAG 日志
docker compose logs -f rag
```

## 项目结构

```
personal-knowledge-rag/
├── main.py              # 交互式命令行入口
├── api.py               # FastAPI Web服务入口
├── rag_engine.py        # RAG核心引擎
├── hybrid_search.py     # BM25+向量混合检索
├── load_cli.py          # 命令行加载工具
├── templates/
│   └── index.html       # Web UI页面
├── requirements.txt     # 依赖列表
├── .env.example         # 环境变量示例
├── Dockerfile           # Docker构建文件
├── video_knowledge/     # 视频精炼内容目录
├── chroma_db/           # 本地向量数据库持久化（开发模式）
└── logs/                # 日志目录
```

## 技术栈

- **LangChain**: RAG 框架
- **ChromaDB**: 向量数据库（远程容器或本地持久化）
- **FastAPI**: Web 服务
- **Anthropic SDK**: 对接 MiniMax M2.7（Anthropic 兼容接口）
- **SiliconFlow**: Embedding 服务（BAAI/bge-large-zh-v1.5）
