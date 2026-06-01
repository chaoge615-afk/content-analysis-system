# 智能内容分析系统 - 项目约束

## 项目概述
B站 UP主 视频 → 自动下载转写 → LLM精炼 → 结构化入库(DuckDB) + 向量化入库(ChromaDB) → 统一入口智能问答

## 当前状态（2026-06-01）
- Phase 1-11 全部完成 ✅
- **内容域分离**：情感(`emotional`) + 求职(`career`) 双轨精炼 + 检索隔离（`refiner_domains.py`）
- **unknown 归属修复**：yt-dlp + Cookie，1158 → 9（99.2%）
- **分批采集**：下载→转写→精炼入库→清理，每批30个，避免磁盘浪费
- **UP主导入导出**：ZIP 打包完整数据（配置+元数据+向量+转写），跨环境一键迁移
- **GPU 转录集成**：采集流程自动委托 gpu-service（GPU > 云ASR > CPU 三级回退）
- 详细进度见 `docs/开发计划.md`

## 技术栈
- Python 3.11 / Node.js 24
- LLM: MiniMax M2.7 (Anthropic API) + DeepSeek V4 Pro (OpenAI API, 精炼+RAG)
- Embedding: SiliconFlow API (BAAI/bge-large-zh-v1.5)
- 精炼: deepseek-v4-pro (local proxy 10.168.165.50:3300)
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

## 新会话启动流程
1. `git pull --rebase`
2. 读取 `docs/开发计划.md` 找到剩余任务
3. 读取 `docs/开发者快速上手指南.md` 了解坑点
4. 开始开发
