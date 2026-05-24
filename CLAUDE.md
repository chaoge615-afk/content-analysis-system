# 智能内容分析系统 - 项目约束

## 项目概述
B站情感博主视频 → 自动下载转写 → LLM精炼 → 结构化入库(DuckDB) + 向量化入库(ChromaDB) → 统一入口智能问答

## 技术栈
- Python 3.11 / Node.js 24 / Git 2.53
- LLM: MiniMax M2.7 (Anthropic-compatible API at api.minimaxi.com/anthropic)
- Embedding: SiliconFlow API (BAAI/bge-large-zh-v1.5)
- 精炼模型: deepseek-v4-pro (via local proxy at 10.168.165.50:3300)
- 存储: DuckDB (结构化) + ChromaDB (向量)
- 部署: Docker Compose (NAS: Intel N150 + 8GB RAM, Local: RTX 4060 + 24GB)

## 子项目
- `bilibili-monitor/` - B站监控 (Hermes Skill, 待独立化改造)
- `personal-knowledge-rag/` - 视频知识库RAG问答 (FastAPI:8090, LangChain, BM25+向量混合检索)
- `text-to-sql/` - Text-to-SQL (FastAPI:8010 + React前端:3000, 4-Agent pipeline)
- `relationship-analysis/` - 情感分析技能 (1413个精炼文件, BM25+向量检索)

## 开发规范
- 环境差异走 .env + Docker profiles, 不改代码
- 所有API密钥走环境变量, 不硬编码
- Git提交用中文说明
- 代码注释用中文
- NAS内存限制8GB, 各服务需设mem_limit
- **Docker 构建必须使用国内镜像加速**：
  - apt: 阿里云 Debian 镜像 (`mirrors.aliyun.com`)
  - pip: 清华 TUNA 镜像 (`pypi.tuna.tsinghua.edu.cn/simple/`)
  - npm: 淘宝镜像 (`registry.npmmirror.com`)
- **每完成一个任务点，立即更新 `开发计划.md` 中的 checkbox，然后 git commit 并 push**

## 关键文件
- `refine_batch.py` - 精炼脚本 (三段式: 核心观点+案例摘要+可行动建议, 31个分类)
- `开发计划.md` - 7个Phase开发任务
- `智能内容分析系统-*.md` - 架构/工作流/部署文档

## 注意事项
- text-to-sql 声称用CrewAI但实际是纯Python手写pipeline
- bilibili-monitor 依赖Hermes平台, 需改造为独立服务
- 已有1413个精炼txt文件在 relationship-analysis/references/情感素材库/
- Docker Desktop 路径: /c/Users/25022/AppData/Local/Programs/DockerDesktop/resources/bin
