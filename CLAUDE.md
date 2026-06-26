# 智能内容分析系统 - 项目约束

## 项目概述
B站 UP主 视频 → 自动下载转写 → LLM精炼 → 结构化入库(DuckDB) + 向量化入库(ChromaDB) → 统一入口智能问答

## 当前状态（2026-06-25）
- Phase 1-11 全部完成 ✅
- **内容域分离**：情感(`emotional`) + 求职(`career`) 双轨精炼 + 检索隔离（`refiner_domains.py`）
- **unknown 归属修复**：yt-dlp + Cookie，1158 → 9（99.2%）
- **分批采集**：下载→转写→精炼入库→清理，每批30个，避免磁盘浪费
- **UP主导入导出**：ZIP 打包完整数据（配置+元数据+向量+转写），跨环境一键迁移
- **GPU 转录集成**：采集流程自动委托 gpu-service（GPU > 云ASR > CPU 三级回退）
- 详细进度见 `docs/开发计划.md`
- [x] K-06: 清理可疑 hacked 表
- [x] K-11: text-to-sql 查询质量优化（UP主LIKE模糊匹配 + play_count字段 + 时间WHERE过滤）
- [x] CS-45/CS-09/CS-07/CS-25: 遗留问题修复第二轮（2026-06-26，详见下方表）

## 已知修复（2026-06-26 遗留问题修复第二轮）
| 编号 | 修复内容 |
|------|---------|
| CS-45 | SQL 超时过短：`mcp-servers/sql_mcp_server.py` 默认 `SQL_TIMEOUT` 60→300 + 结构化 Timeout(connect短/read长)；`docker-compose.yml` mcp-servers 注入 `SQL_TIMEOUT=360`、router-agent `REQUEST_TIMEOUT` 120→360（底层 pipeline 实测 157-342s，60/120s 必超时）。**改超时务必同步 router-agent 主路径，否则 MCP 不超时但 router 先断** |
| CS-09 | DuckDB 缺 video_meta 表：新建 `text-to-sql/src/database/schema.sql`（含 domain 列，与 db_writer 对齐）；`duckdb_utils.init_database` 兜底内联 DDL + 列迁移（补 domain/play_count）；`api_server.py` lifespan 自举建表（弃用 `@on_event("startup")`），容器启动即建表/迁移，不再依赖 bilibili-monitor 实跑。**`.gitignore` 已加例外 `!text-to-sql/src/database/schema.sql`，源码 SQL 必须入库** |
| CS-07 | execute_sql 无白名单：`duckdb_utils._assert_readonly_sql` 仅允许 SELECT/WITH 首关键字 + 注释剥离 + 多语句拒绝。**不要加全文关键字黑名单**（会误伤 `WHERE title LIKE '%DROP%'`），首关键字白名单已足够防 DDL/DML。建表/get_table_info/get_all_schemas 走 `conn.execute` 直连已豁免 |
| CS-25 | RAG top_k 三层未贯通：`rag_mcp_server.semantic_search` 签名默认 `top_k=None`（非5，避免走 MCP 路径覆盖 env TOP_K）；`api.py` `AskVideoRequest` 加 `Optional[int] top_k`；`rag_engine.ask_video` + `_hybrid_search_video` 透传 `effective_top_k`，上限 `min(top_k,20)` **仅钳请求级，不钳 env 默认** |

## 技术栈
- Python 3.11 / Node.js 24
- LLM: MiniMax M2.7 (Anthropic API) + DeepSeek V4 Flash (OpenAI API, 精炼+RAG)
- Embedding: SiliconFlow API (BAAI/bge-large-zh-v1.5)
- 精炼: deepseek-v4-flash (DeepSeek 官方 API)
- 存储: DuckDB (结构化) + ChromaDB (向量)
- 部署: Docker Compose (NAS: N150 8GB, Local: RTX 4060)

## 子项目
| 目录 | 说明 | 端口 |
|------|------|------|
| `bilibili-monitor/` | B站监控（下载+转写+精炼） | — |
| `personal-knowledge-rag/` | RAG问答（BM25+向量混合检索） | 8090 |
| `text-to-sql/` | Text-to-SQL（4-Agent pipeline） | 8010 |
| `router-agent/` | 路由Agent（意图分类+分发+融合） | 8000 |
| `text-to-sql/frontend/` | 统一前端（React + Nginx） | 80 |

## 开发规范
- **开始任何开发前，必须先 `git pull --rebase`**（多会话交替修改，远程是唯一真实来源）
- **启动项目前，确认是否需要重新构建**：对比本地代码与运行中镜像的构建时间，如果代码有更新（git pull 有新提交），先 `docker compose --profile dev up -d --build` 重建镜像再启动
- **gpu-service 走独立 profile**：`--profile dev` 不含 gpu-service。有 NVIDIA GPU 的机器用 `./scripts/deploy.sh dev`（脚本会实测 `--gpus all`，自动追加 `--profile gpu`）；或手动 `docker compose --profile dev --profile gpu up -d --build`。无 GPU 机器直接 `--profile dev` 即可，不会构建/启动 gpu-service
- **修改代码后，先重建Docker镜像、重启服务、验证功能，确认无误后再 git commit 并 push**
- 环境差异走 .env + Docker profiles，不改代码
- API密钥走环境变量，不硬编码
- Git提交/代码注释用中文
- NAS内存8GB，各服务需设mem_limit
- Docker 构建用国内镜像：apt(阿里云) pip(清华TUNA) npm(淘宝)
- 镜像重建后清缓存：`docker builder prune -a -f`
- 每完成任务点，更新 `docs/开发计划.md` 的 checkbox

## 关键文件
- `docs/开发计划.md` - 任务清单和进度
- `docs/开发者快速上手指南.md` - 隐性知识、调试技巧、已知坑点
- `README.md` - 项目概述

## 注意事项
- text-to-sql 声称用CrewAI但实际是纯Python手写pipeline
- 意图分类器 category 只能用有效分类名，话题词放 keywords
- Docker Desktop 路径: /c/Users/25022/AppData/Local/Programs/DockerDesktop/resources/bin
- **video_meta 表含 `play_count` + `domain` 列**：play_count 播放量；domain 内容域（emotional/career）。列漂移由 `duckdb_utils.init_database` 启动时自动迁移补列
- **text-to-sql 启动自举建表**：`api_server.py` lifespan 调 `init_database()`，容器启动即建 video_meta/up_info/query_log + 迁移列，不再依赖 bilibili-monitor 实跑。schema 源在 `src/database/schema.sql`
- **execute_sql 只读白名单**：仅允许 SELECT/WITH，DROP/DELETE/UPDATE 等被 `_assert_readonly_sql` 硬拦。写操作不能复用 execute_sql
- **RAG top_k 请求级覆盖**：MCP/HTTP 传 top_k 覆盖该次检索；不传用 env `TOP_K` 默认。上限 20 仅钳请求级
- **text-to-sql Prompt 优化（K-11）**：UP主名称查询使用 `LIKE` 模糊匹配（避免精确匹配失败）；时间范围表达映射为 SQL `WHERE` 条件（如"最近"→ 时间过滤）；播放量字段使用 `play_count`

## 新会话启动流程
1. `git pull --rebase`
2. 读取 `docs/开发计划.md` 找到剩余任务
3. 读取 `docs/开发者快速上手指南.md` 了解坑点
4. 开始开发
