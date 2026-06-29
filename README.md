# 智能内容分析系统

![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Node](https://img.shields.io/badge/Node.js-24-green?logo=node.js)
![License](https://img.shields.io/badge/License-MIT-yellow)

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
# 推荐：脚本实测 GPU 后自动追加 --profile gpu
./scripts/deploy.sh dev

# 或手动指定
docker compose --profile dev --profile gpu up -d --build
```
gpu-service 走独立 `gpu` profile，需 NVIDIA GPU + CUDA 直通；无 GPU 机器用 `--profile dev` 即可，不会构建/启动 gpu-service（转写自动回退云ASR/CPU）。

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
B站视频自动采集：拉取视频列表 → yt-dlp 下载 → 转写（GPU > 云ASR > CPU 三级回退）→ DeepSeek 精炼 → 写入 DuckDB + ChromaDB。采集时从 Bilibili API 获取播放量（play_count）并写入 video_meta（含 domain 内容域列）。支持 UP主 导入导出（ZIP 打包跨环境迁移）。已清理 DuckDB 中被篡改的可疑表（K-06）。

### personal-knowledge-rag/
视频知识库 RAG 问答：BM25 + 向量混合检索，支持 MiniMax / DeepSeek 双 LLM，31 个情感分类 metadata 过滤。top_k 支持请求级覆盖（MCP/HTTP 传参，不传用 env TOP_K 默认，上限 20 仅钳请求级）

### text-to-sql/
自然语言转 SQL 查询：4-Agent pipeline（schema → intent → SQL 生成 → 执行），前端 React 对话界面。支持 UP主 名称模糊匹配（LIKE）、play_count 播放量字段查询、时间范围 WHERE 条件生成。**容器启动自举建表**（lifespan 调 init_database，建 video_meta/up_info/query_log + 列迁移，不再依赖 bilibili-monitor 实跑）；**execute_sql 只读白名单**（仅 SELECT/WITH，DDL/DML 硬拦）

### router-agent/
统一入口：意图分类（structured / semantic / hybrid）→ 分发到 Text-to-SQL 或 RAG → hybrid 模式 LLM 融合结果。支持 UP主 名称标准化（简称→全名，如"桃姐"→"恋爱教头桃姐"），智能降级（SQL 空结果自动回退到 RAG 内容）

## 技术栈

- **LLM**: MiniMax M2.7 (Anthropic API) + DeepSeek V4 Flash (OpenAI API)
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

## 已知限制

| 限制项 | 说明 |
|--------|------|
| 多用户 | 单用户模式，无登录/权限隔离 |
| 视频播放 | 仅存储音频转写文本，不支持在线播放原视频 |
| 流式响应 | LLM 回答为一次性返回，无 SSE/WebSocket 流式输出 |
| 高并发 | 单实例部署，未做负载均衡，不适合多人同时使用 |
| Cookie 续期 | B站 Cookie 有效期约 30 天，过期需手动更新 |

## 开发规范

- 环境差异走 `.env` + Docker profiles，不改代码
- 所有 API 密钥走环境变量，不硬编码
- Docker 构建使用国内镜像加速（apt: 阿里云, pip: 清华 TUNA, npm: 淘宝）
- 每次镜像重建后执行 `docker builder prune -a -f` 清理缓存（**已自动化**：走 `./scripts/deploy.sh` 的重建由脚本收尾自动执行 `docker image prune -f` + `docker builder prune -a -f`；手敲 `up -d --build` 由计划任务 `DockerAutoCleanup` 每周日 03:00 兜底，也可随时双击工作目录根 `docker-cleanup.bat`；镜像清理只用 `image prune -f` 清悬空旧版，禁用 `-a` 以免误删 bilibili-monitor/gpu-service 等按需服务镜像）

## 修复记录（2026-06-26 第二轮·遗留问题）

> 基于 6 组诊断 + 6 组对抗审查（共 12 Agent）的修复方案，方案详见 [遗留问题修复方案.md](遗留问题修复方案.md)，全部经回归验证通过。

| 编号 | 子项目 | 修复内容 | 回归验证 |
|------|--------|----------|----------|
| CS-45 | mcp-servers / router-agent | SQL 超时过短：`sql_mcp_server.py` 默认 `SQL_TIMEOUT` 60→300 + 结构化 Timeout；`docker-compose.yml` mcp-servers `SQL_TIMEOUT=360`、router-agent `REQUEST_TIMEOUT` 120→360 | env 注入均=360 |
| CS-09 | text-to-sql | DuckDB 缺 video_meta：新建 `src/database/schema.sql`（含 domain 列）；`init_database` 兜底 DDL + 列迁移；`api_server.py` lifespan 自举建表 | 启动日志「迁移：video_meta 补 domain 列」，列含 domain，/api/tables 含 video_meta |
| CS-07 | text-to-sql | execute_sql 无白名单：`_assert_readonly_sql` 仅 SELECT/WITH 首关键字 + 注释剥离 + 多语句拒绝（不加全文黑名单，避免误伤 `LIKE '%DROP%'`） | 9/9 单测通过（DROP/DELETE/UPDATE/CREATE/注释绕过/多语句均拦，含 LIKE '%DROP%' 的 SELECT 放行） |
| CS-25 | rag / mcp-servers | top_k 三层未贯通：MCP 签名默认 None（非5）→ api Optional[int] → engine effective_top_k（上限仅钳请求级） | top_k=2 sources=2 / top_k=15 sources=4，随 top_k 单调变化（原恒为3） |
