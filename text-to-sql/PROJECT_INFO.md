# Text-to-SQL Multi-Agent System

## 项目简介

一个基于大语言模型的 Text-to-SQL 系统，可以将自然语言问题转换为 SQL 查询。系统采用多 Agent 协作架构，支持 Web 界面和 CLI 两种交互方式。

## 技术架构

### 技术栈
- **语言**: Python 3.11 + TypeScript
- **数据库**: DuckDB (嵌入式关系型数据库)
- **Agent 框架**: CrewAI
- **大模型**: MiniMax M2.7 (Anthropic 兼容接口)
- **前端**: React 18 + Vite + TailwindCSS
- **后端 API**: FastAPI

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面                              │
│  ┌─────────────────┐        ┌─────────────────────────┐   │
│  │   Web 界面      │        │      CLI 交互模式         │   │
│  │  (React+Vite)  │        │  (python -m src.main)   │   │
│  └────────┬────────┘        └───────────┬─────────────┘   │
└───────────┼─────────────────────────────┼───────────────────┘
            │                             │
            ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      API 层                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              FastAPI Server (:8010)                  │   │
│  │  - POST /query     处理查询请求                      │   │
│  │  - GET  /          健康检查                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent 编排层                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐│
│  │ 意图理解  │──▶│Schema检索│──▶│SQL 生成  │──▶│SQL 审查  ││
│  │  Agent   │   │  Agent   │   │  Agent   │   │  Agent   ││
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘│
│                                            │              │
│                                    审查通过 │              │
│                                     ◀──────┘              │
│                                            │              │
│                                   审查失败 │ 最多3次      │
│                                     ──────▶ [重新生成]     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据层                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              DuckDB (content.db)                    │   │
│  │  - video_meta 表    视频元数据                       │   │
│  │  - up_info 表       UP主信息                        │   │
│  │  - query_log 表     查询日志                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Agent 详细说明

### Agent 1: 意图理解
**文件**: `src/agents/intent_agent.py`

解析用户问题，提取：
- 查询类型 (video)
- 查询目标 (video_count/video_list/up_info/category_stats/video_summary)
- 时间范围 (recent/this_week/this_month)
- 聚合方式 (count/avg)
- 筛选条件 (up_name, category, date_range)

### Agent 2: Schema 检索
**文件**: `src/agents/schema_agent.py`

根据意图确定：
- 需要查询的表
- 需要查询的字段
- 表之间的 JOIN 关系

### Agent 3: SQL 生成
**文件**: `src/agents/sql_gen_agent.py`

生成 DuckDB 兼容的 SQL 语句

### Agent 4: SQL 审查
**文件**: `src/agents/review_agent.py`

检查维度：
- 语法正确性
- 逻辑正确性
- 性能检查
- 安全性

## 项目文件结构

```
text-to-sql/
├── src/
│   ├── main.py              # CLI 入口
│   ├── config.py            # 配置管理 (从 .env 加载)
│   ├── llm_client.py        # MiniMax LLM 客户端
│   ├── api_server.py        # FastAPI HTTP 服务器
│   ├── database/
│   │   ├── schema.sql       # 数据库 DDL
│   │   └── duckdb_utils.py  # 数据库工具函数
│   ├── agents/
│   │   ├── intent_agent.py     # 意图理解
│   │   ├── schema_agent.py     # Schema 检索
│   │   ├── sql_gen_agent.py    # SQL 生成
│   │   └── review_agent.py     # SQL 审查
│   ├── orchestrator/
│   │   └── pipeline.py         # 主编排流程 + 回退机制
│   └── prompts/
│       └── templates.py        # 各 Agent 的 Prompt 模板
├── frontend/
│   ├── src/
│   │   ├── components/         # React 组件
│   │   │   ├── QueryInput.tsx  # 问题输入组件
│   │   │   └── ResultTable.tsx # 结果表格组件
│   │   ├── services/
│   │   │   └── api.ts          # API 调用服务
│   │   ├── App.tsx             # 主应用组件
│   │   └── main.tsx            # 前端入口
│   ├── package.json
│   ├── vite.config.ts          # Vite 配置 (代理 /api 到后端)
│   └── tailwind.config.js      # Tailwind CSS 配置
├── tests/
│   └── test_pipeline.py         # 流程测试
├── data/
│   └── content.db               # DuckDB 数据库
├── .env                         # 环境配置
├── requirements.txt             # Python 依赖
└── README.md                    # 项目说明
```

## 关键配置

### .env 文件
```env
MINIMAX_API_KEY=<your_api_key>
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MODEL_NAME=MiniMax-M2.7
DATABASE_PATH=./data/content.db
MAX_RETRIES=3
```

### 端口配置
- 后端 API: 8010
- 前端 Dev: 3000
- Vite 代理: `/query` -> `http://localhost:8010`

## 启动方式

### 开发模式
```bash
# 终端 1: 后端
python -m src.api_server

# 终端 2: 前端
cd frontend && npm run dev
```

### CLI 模式
```bash
python -m src.main --interactive
python -m src.main "桃姐这个月发了几个视频？"
```

### Docker
```bash
docker-compose up --build
```

## 注意事项

1. **API Key**: 需要有效的 MiniMax API Key
2. **数据库**: 首次运行需要初始化 `python -m src.main --init`
3. **模型**: 当前使用 MiniMax-M2.7，需确认 API 支持
4. **回退机制**: SQL 审查失败会自动重试，最多 3 次

## 开发记录

| 日期 | 内容 |
|------|------|
| 2026-04-20 | 初始化项目，实现 4 个 Agent + CLI |
| 2026-04-20 | 添加 FastAPI 服务器和 React 前端 |
| 2026-04-20 | 推送到 GitHub master 分支 |
| 2026-04-20 | Docker 部署配置修复与调试 |
| 2026-04-21 | 前后端分离部署，端口改为 8010 |
| 2026-04-21 | 前后端合并为单个 Docker 容器 |

## 2026-04-21 工作记录

### 已完成

1. **前后端分离部署到合并**
   - 修改端口配置：8000 → 8010
   - 前端使用 `VITE_API_URL=http://api:8010` 访问后端
   - 后因 Docker 网络问题，改为前后端合并到单个容器

2. **前后端合并部署**
   - 修改 Dockerfile 安装 Node.js
   - 添加 `start.sh` 脚本同时运行 uvicorn 和 vite
   - 前端 Vite 代理配置为 `http://localhost:8010`
   - 解决 IPv4/IPv6 绑定问题 (`--host 0.0.0.0`)

3. **API 端口问题修复**
   - Dockerfile 中 `--host ::` 改为 `--host 0.0.0.0`
   - 解决 Uvicorn 绑定到 IPv6 导致宿主机无法访问的问题

4. **前端请求配置**
   - `api.ts` 使用相对路径 `/` 通过 Vite 代理访问后端
   - 避免浏览器直接访问后端跨域问题

### 当前部署架构

```
┌─────────────────────────────────────┐
│         Docker 容器 (text-to-sql-app)  │
│                                     │
│  ┌─────────────┐  ┌─────────────┐  │
│  │  Vite (3000) │  │ Uvicorn     │  │
│  │  前端开发服务器 │  │ (8010)     │  │
│  └──────┬──────┘  └──────┬──────┘  │
│         │                │         │
│         └──────┬─────────┘         │
│              localhost              │
└─────────────────────────────────────┘
         │                │
         ▼                ▼
   http://localhost:3000  http://localhost:8010
```

### 剩余问题

#### 1. MiniMax API 服务器过载 (间歇性)
- **现象**: 返回 `overloaded_error` (529 错误)
- **原因**: MiniMax API 服务端负载过高
- **影响**: 查询请求会返回"服务暂时繁忙"错误
- **解决**: 等待 MiniMax 服务恢复后重试

### 已解决

#### 2. 前端域名访问限制
- **现象**: 浏览器访问域名时报错 `Blocked request. This host is not allowed`
- **原因**: Vite 默认不允许非 localhost 域名访问
- **解决**: 在 `vite.config.ts` 中添加 `allowedHosts` 配置，支持 IPv4/IPv6 双栈监听

```typescript
server: {
  host: '::',  // 同时监听 IPv4 和 IPv6
  port: 3000,
  allowedHosts: ['www.speedtest.ah.cn', 'speedtest.ah.cn'],
  proxy: {
    '/query': {
      target: 'http://localhost:8010',
      changeOrigin: true,
    },
  },
}
```

### 当前配置

**.env 配置**:
```env
MINIMAX_API_KEY=<your_key>
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MODEL_NAME=MiniMax-M2.7
DATABASE_PATH=./data/content.db
MAX_RETRIES=3
```

**端口配置**:
- 后端 API: 8010
- 前端 Dev: 3000
- Vite 代理: `/query` → `http://localhost:8010`

### 启动命令

```bash
# 前后端合并启动 (新版 Docker)
docker compose up --build

# 旧版 Docker
docker-compose up --build

# 测试 API
curl http://localhost:8010/

# 测试查询
curl -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question": "桃姐这个月发了几个视频？"}'
```
