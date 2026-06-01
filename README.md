# 智能内容分析系统

B站情感博主视频 → 自动下载转写 → LLM 精炼 → 结构化入库(DuckDB) + 向量化入库(ChromaDB) → 统一入口智能问答

## 架构

```
bilibili-monitor          personal-knowledge-rag        text-to-sql
(下载+转写+精炼)     →    (向量检索 RAG)              (结构化 SQL 查询)
        ↓                        ↓                          ↓
    DuckDB + ChromaDB ←──────── router-agent ←──── 前端 (React+Nginx)
                          (意图分类+查询分发)
```

### 服务列表

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 80 | React 前端 + Nginx 反向代理 |
| router-agent | 8000 | 意图分类 + 查询分发 + 结果融合 |
| text-to-sql | 8010 | 4-Agent pipeline 结构化查询 |
| rag | 8090 | BM25 + 向量混合语义检索 |
| chromadb | 8001 | ChromaDB 向量数据库 |
| bilibili-monitor | — | 按需运行（非常驻服务） |
| bilibili-cron | — | 定时调度（每 6 小时，仅 NAS） |
| gpu-service | 8011 | GPU 转录服务（仅 dev profile，需 NVIDIA 显卡） |

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/chaoge615-afk/content-analysis-system.git
cd content-analysis-system
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入必要的 API Key：

| 变量 | 用途 | 必填 |
|------|------|------|
| `SILICONFLOW_API_KEY` | SiliconFlow Embedding API | 是 |
| `MINIMAX_API_KEY` | MiniMax LLM（意图分类、SQL 生成） | 是 |
| `REFINE_API_KEY` + `REFINE_API_URL` | DeepSeek（内容精炼、RAG 问答） | 是 |
| `BILIBILI_COOKIE` | B站 Cookie（视频下载） | 采集时需要 |
| `QQ_BOT_URL` + `QQ_USER_ID` | QQ 通知（可选） | 否 |

### 3. 启动服务

**开发环境：**
```bash
docker compose --profile dev up -d --build
```

**生产环境（NAS）：**
```bash
docker compose --profile nas up -d --build
```

NAS 模式额外包含 `bilibili-cron` 定时调度容器（每 6 小时自动运行 bilibili-monitor）。

**GPU 转录（开发机，需 NVIDIA 显卡）：**
```bash
docker compose --profile dev up -d --build
```
Dev 模式额外包含 `gpu-service` 容器（端口 8011），前端管理面板可直接触发 GPU 转录。

### 4. 访问

- 前端界面：http://localhost
- Router API：http://localhost:8000/api/chat
- RAG API：http://localhost:8090/api/stats
- Text-to-SQL API：http://localhost:8010

## 使用方式

### 问答（通过 Router Agent）

```bash
# 语义查询
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "如何追女生"}'

# 结构化查询
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "知识库有多少个视频"}'

# 强制路由
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "冷暴力怎么处理", "force_route": "rag"}'
```

### 手动运行 bilibili-monitor

```bash
docker compose run --rm bilibili-monitor
```

### 迁移已有精炼数据

```bash
docker compose run --rm bilibili-monitor python src/migrate_refined.py
```

## 子项目说明

### bilibili-monitor/
B站视频自动采集：拉取视频列表 → yt-dlp 下载 → 转写（GPU > 云ASR > CPU 三级回退）→ DeepSeek 精炼 → 写入 DuckDB + ChromaDB。支持 UP主 导入导出（ZIP 打包跨环境迁移）。

### personal-knowledge-rag/
视频知识库 RAG 问答：BM25 + 向量混合检索，支持 MiniMax / DeepSeek 双 LLM，31 个情感分类 metadata 过滤

### text-to-sql/
自然语言转 SQL 查询：4-Agent pipeline（schema → intent → SQL 生成 → 执行），前端 React 对话界面

### router-agent/
统一入口：意图分类（structured / semantic / hybrid）→ 分发到 Text-to-SQL 或 RAG → hybrid 模式 LLM 融合结果。支持 UP主 名称标准化（简称→全名，如"桃姐"→"恋爱教头桃姐"），智能降级（SQL 空结果自动回退到 RAG 内容）

## 技术栈

- **LLM**: MiniMax M2.7 (Anthropic API) + DeepSeek V4 Pro (OpenAI API)
- **Embedding**: SiliconFlow (BAAI/bge-large-zh-v1.5)
- **存储**: DuckDB (结构化) + ChromaDB (向量)
- **转写**: faster-whisper (CTranslate2, GPU/CPU) + 硅基流动云 ASR (SenseVoiceSmall)
- **部署**: Docker Compose, profiles 区分环境

## Docker 镜像迁移

如果需要在新机器上部署且不想重新构建：

```bash
# 当前机器导出
docker save ai-rag ai-text-to-sql ai-router-agent ai-frontend ai-bilibili-monitor -o images.tar

# 新机器加载
docker load -i images.tar
docker compose --profile dev up -d
```

## 目录结构

```
├── docker-compose.yml          # 统一编排
├── .env.example                # 环境变量模板
├── shared/shared_embeddings.py  # 共享 Embedding 模块
├── shared/shared_config.py      # 共享配置加载
├── bilibili-monitor/           # B站视频采集
├── personal-knowledge-rag/     # 视频知识库 RAG
├── text-to-sql/                # Text-to-SQL 服务
│   └── frontend/               # React 前端
├── router-agent/               # 路由分发
└── scripts/                    # 全局脚本
    └── cron_monitor.sh         # 宿主机 cron 入口（备选方案）
```

## 开发规范

- 环境差异走 `.env` + Docker profiles，不改代码
- 所有 API 密钥走环境变量，不硬编码
- Docker 构建使用国内镜像加速（apt: 阿里云, pip: 清华 TUNA, npm: 淘宝）
- 每次镜像重建后执行 `docker builder prune -a -f` 清理缓存
