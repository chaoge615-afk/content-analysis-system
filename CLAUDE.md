# 智能内容分析系统 - 项目约束

## 项目概述
B站情感博主视频 → 自动下载转写 → LLM精炼 → 结构化入库(DuckDB) + 向量化入库(ChromaDB) → 统一入口智能问答

## 当前状态（2026-05-27）
- Phase 1-8 全部完成（133/133 任务）✅
- Phase 9 进行中（混合转录架构：NAS下载 + 开发机GPU转录 + 飞牛Sync）
  - **9.2 Docker GPU 直通完成**：`gpu-service` 容器自动启动，RTX 4060 (8188MB) CUDA 12.4 直通验证通过
- **Phase 10 完成**（前端 UP主管理 + NAS 云 ASR 转写，17/17 任务）✅
  - **UP主管理**：前端输入 B站链接 → 解析预览（名称/UID/头像）→ 选模型 → 写入 YAML 配置
  - **云 ASR 转写**：硅基流动 SenseVoiceSmall（免费）替代本地 Whisper，JSON 设置/用量存储 + 预算上限 + 手动开关
  - 新增模块：`up_manager.py`、`asr_manager.py`、`transcribe_asr.py`
  - 新增 API：7 个端点（UP主 4 + ASR 3）
  - 新增组件：`UpManager.tsx`、GpuTranscribe ASR 区域
- P0 完成：bilibili-monitor 全流程验证通过
- P1 完成：checkpoint 简化（UID 命名）+ SDK 统一（Anthropic）
- P2 完成：采集触发按钮 + 查询日志可视化 + 服务监控仪表盘
- **今日优化（2026-05-26）**：
  - Cookie 管理增强：前端保存/删除/测试 Cookie（B站 nav API 验证）、采集前预检
  - Cookie 注入修复：直接传内容而非文件路径（修复 volume 名不匹配问题）
  - 服务监控优化：SQL统计改DuckDB直查 + Docker stats并行采集（23s→2.2s）
  - 快捷指令美化：新增 QuickView 组件，结构化展示 status/up_list/recent/categories
  - **Token 优化**：Prompt Caching 全面启用（90% 折扣）、消除冗余 LLM 调用（每次查询减少 2 次）、QueryLogger 独立数据库修复 DuckDB 锁冲突
  - **Docker GPU 直通**：Dockerfile.gpu + docker-compose gpu-service + NVIDIA GPU 直通，`docker compose --profile dev up -d` 自动启动
- 前端新增管理面板（Tab 切换：对话 / 管理面板）
- router-agent 新增 Docker socket 挂载 + docker SDK（用于触发 bilibili-monitor 容器）
- Docker 部署验证通过（6 个服务全部正常运行，含 gpu-service）

## 技术栈
- Python 3.11 / Node.js 24 / Git 2.53
- LLM: MiniMax M2.7 (Anthropic-compatible API at api.minimaxi.com/anthropic)
- LLM: DeepSeek V4 Pro (OpenAI-compatible API, RAG 问答默认 + 内容精炼)
- Embedding: SiliconFlow API (BAAI/bge-large-zh-v1.5)
- 精炼模型: deepseek-v4-pro (via local proxy at 10.168.165.50:3300)
- 存储: DuckDB (结构化) + ChromaDB (向量)
- 部署: Docker Compose (NAS: Intel N150 + 8GB RAM, Local: RTX 4060 + 24GB)

## 子项目
- `bilibili-monitor/` - B站监控（已独立化，无 Hermes 依赖）
- `personal-knowledge-rag/` - 视频知识库RAG问答 (FastAPI:8090, LangChain, BM25+向量混合检索, DeepSeek/MiniMax 双 LLM)
- `text-to-sql/` - Text-to-SQL (FastAPI:8010 + React前端:3000, 4-Agent 手写pipeline)
- `router-agent/` - 路由 Agent（意图分类 + 查询分发 + 结果融合, FastAPI:8000）
- `text-to-sql/frontend/` - 统一前端（React + Nginx 反向代理, :80）
- `relationship-analysis/` - 情感分析技能 (1413个精炼文件源, 已迁移到主系统)

## 开发规范
- **开始任何开发前，必须先执行 `git pull --rebase` 确认代码是最新版本**（项目由多个 Claude Code 会话交替修改，远程仓库是唯一真实来源）
- 环境差异走 .env + Docker profiles, 不改代码
- 所有API密钥走环境变量, 不硬编码
- Git提交用中文说明
- 代码注释用中文
- NAS内存限制8GB, 各服务需设mem_limit
- **Docker 构建必须使用国内镜像加速**：
  - apt: 阿里云 Debian 镜像 (`mirrors.aliyun.com`)
  - pip: 清华 TUNA 镜像 (`pypi.tuna.tsinghua.edu.cn/simple/`)
  - npm: 淘宝镜像 (`registry.npmmirror.com`)
- **每次 Docker 镜像重建后，清理构建缓存**：`docker builder prune -a -f`（释放磁盘空间）
- **每完成一个任务点，立即更新 `开发计划.md` 中的 checkbox，同时检查并更新工作空间内其他相关 .md 文档（如 README.md、架构文档、快速上手指南等），然后 git commit 并 push**
- 完成开发后立即 push，避免本地未提交的改动与其他会话冲突

## 关键文件
- `开发计划.md` - 任务清单和进度（剩余任务在 Phase 8.5）
- `开发者快速上手指南.md` - 隐性知识、常见问题、调试技巧
- `README.md` - 项目概述、快速开始
- `智能内容分析系统-*.md` - 架构/工作流/部署规划
- `refine_batch.py` - 精炼脚本 (三段式: 核心观点+案例摘要+可行动建议, 31个分类)

## 注意事项
- text-to-sql 声称用CrewAI但实际是纯Python手写pipeline
- bilibili-monitor 已从 Hermes Skill 改造为独立服务，无 Hermes 依赖
- 意图分类器 category 只能用 31 个有效分类名（如 `01_喜欢`），话题词（如"冷暴力"）放 keywords
- Docker Desktop 路径: /c/Users/25022/AppData/Local/Programs/DockerDesktop/resources/bin

## 新会话启动流程
1. `git pull --rebase`（确保最新）
2. 读取 `开发计划.md`，找到剩余任务
3. 读取 `开发者快速上手指南.md` 了解调试技巧和已知坑点
4. 开始开发
