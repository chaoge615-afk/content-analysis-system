# Text-to-SQL Multi-Agent System

基于 CrewAI 和 MiniMax 的自然语言转 SQL 查询系统，支持 Web 界面。

## 技术栈

| 项目 | 选择 |
|------|------|
| 编程语言 | Python 3.11 |
| 数据库 | DuckDB |
| Agent 框架 | CrewAI |
| 大模型 | MiniMax (M2.7) |
| 前端框架 | React 18 + TypeScript |
| 后端 API | FastAPI |
| 构建工具 | Vite |
| 样式 | Tailwind CSS |

## 项目结构

```
text-to-sql/
├── src/
│   ├── main.py              # CLI 入口
│   ├── config.py            # 配置管理
│   ├── llm_client.py        # LLM 客户端
│   ├── api_server.py        # FastAPI HTTP 服务器
│   ├── database/
│   │   ├── schema.sql       # 数据库 DDL
│   │   └── duckdb_utils.py  # 数据库工具
│   ├── agents/
│   │   ├── intent_agent.py     # Agent 1: 意图理解
│   │   ├── schema_agent.py     # Agent 2: Schema 检索
│   │   ├── sql_gen_agent.py     # Agent 3: SQL 生成
│   │   └── review_agent.py      # Agent 4: SQL 审查
│   ├── orchestrator/
│   │   └── pipeline.py       # 主编排流程
│   └── prompts/
│       └── templates.py      # Prompt 模板
├── frontend/
│   ├── src/
│   │   ├── components/       # React 组件
│   │   ├── services/         # API 服务
│   │   ├── App.tsx           # 主应用
│   │   └── main.tsx          # 入口
│   └── package.json
├── tests/
│   └── test_pipeline.py     # 单元测试
├── data/
│   └── nutrition.db          # DuckDB 数据库
├── .env                     # API 配置
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 快速开始

### 1. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

编辑 `.env` 文件：

```env
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MODEL_NAME=MiniMax-M2.7
DATABASE_PATH=./data/nutrition.db
```

### 3. 初始化数据库

```bash
python -m src.main --init
```

### 4. 启动服务

**方式一：Web 界面（推荐）**

终端 1 - 启动后端 API：
```bash
python -m src.api_server
```

终端 2 - 启动前端：
```bash
cd frontend
npm install
npm run dev
```

然后访问 http://localhost:3000

**方式二：CLI 交互模式**

```bash
python -m src.main --interactive
```

**方式三：单次查询**

```bash
python -m src.main "今天我吃了多少蛋白质？"
```

## Agent 工作流程

```
用户提问
    ↓
┌─────────────────┐
│  意图理解 Agent   │ → 结构化查询意图
└─────────────────┘
    ↓
┌─────────────────┐
│  Schema 检索 Agent │ → 相关表和字段
└─────────────────┘
    ↓
┌─────────────────┐
│  SQL 生成 Agent   │ → DuckDB SQL
└─────────────────┘
    ↓
┌─────────────────┐
│  SQL 审查 Agent   │ → 通过/不通过
└─────────────────┘
    ↓ (通过)
┌─────────────────┐
│   执行 SQL      │ → 查询结果
└─────────────────┘
    ↓
┌─────────────────┐
│  自然语言回答     │
└─────────────────┘
```

**回退机制：** SQL 审查不通过时，自动重新生成，最多 3 次。

## 数据库 Schema

### food 表（食物营养成分）

| 字段 | 类型 | 含义 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR | 食物名称 |
| calorie | DECIMAL | 每100g热量(kcal) |
| protein | DECIMAL | 每100g蛋白质(g) |
| fat | DECIMAL | 每100g脂肪(g) |
| carb | DECIMAL | 每100g碳水(g) |

### daily_record 表（每日摄入记录）

| 字段 | 类型 | 含义 |
|------|------|------|
| id | INTEGER | 主键 |
| date | DATE | 日期 |
| total_calorie | DECIMAL | 当日总热量 |
| total_protein | DECIMAL | 当日总蛋白质 |
| target_calorie | DECIMAL | 目标热量 |
| target_protein | DECIMAL | 目标蛋白质 |

### meal_record 表（餐次记录）

| 字段 | 类型 | 含义 |
|------|------|------|
| id | INTEGER | 主键 |
| daily_id | INTEGER | 关联 daily_record |
| meal_type | VARCHAR | 早餐/午餐/晚餐/加餐 |
| food_id | INTEGER | 关联 food |
| weight_g | INTEGER | 重量(克) |

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/query` | POST | 提交查询问题 |
| `/` | GET | 健康检查 |

### 查询接口示例

```bash
curl -X POST http://localhost:8010/query \
  -H "Content-Type: application/json" \
  -d '{"question": "今天我吃了多少蛋白质？"}'
```

## 测试

```bash
python tests/test_pipeline.py
```

## Docker 部署

```bash
# 构建并启动（新版 Docker）
docker compose up --build

# 旧版 Docker
docker-compose up --build

# 测试 API
curl http://localhost:8010/
```

访问 http://localhost:3000 使用 Web 界面。

### 域名访问配置

如需通过域名访问，修改 `frontend/vite.config.ts` 中的 `allowedHosts`：

```typescript
server: {
  host: '::',  // 同时监听 IPv4 和 IPv6
  port: 3000,
  allowedHosts: ['your-domain.com'],
  proxy: {
    '/query': {
      target: 'http://localhost:8010',
      changeOrigin: true,
    },
  },
}
```

## 配置说明

所有配置通过 `.env` 文件管理：

```env
# MiniMax API Configuration
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MODEL_NAME=MiniMax-M2.7

# Database Configuration
DATABASE_PATH=./data/nutrition.db

# Agent Configuration
MAX_RETRIES=3
```

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| MINIMAX_API_KEY | MiniMax API Key | (必填) |
| MINIMAX_BASE_URL | API 端点 | https://api.minimaxi.com/anthropic |
| MODEL_NAME | 模型名称 | MiniMax-M2.7 |
| DATABASE_PATH | 数据库路径 | ./data/nutrition.db |
| MAX_RETRIES | SQL 重试次数 | 3 |
