# bilibili-monitor

> B站情感博主视频 → 自动下载 → 语音转写 → LLM 精炼 → 结构化入库(DuckDB) + 向量化入库(ChromaDB) → QQ 通知

**状态**：✅ 已从 Hermes Skill 改造为独立 Docker 服务，无 Hermes 依赖

---

## 目录结构

```
bilibili-monitor/
├── SKILL.md                     # 本文档
├── Dockerfile                   # Docker 镜像构建
├── cron_entry.sh                # bilibili-cron 容器入口脚本
├── config/                      # UP 主配置文件（每个 UP 主一个 yaml）
│   ├── an Jiajia.yaml
│   ├── 3546912280021515.yaml
│   ├── 啊柚的碎碎念.yaml
│   └── 夹性学姐在这.yaml
├── data/                        # Checkpoint 文件（自动生成）
│   ├── <name>_downloaded.txt    # 已下载待转写
│   └── <name>_done_bvid.txt     # 转写完成
└── scripts/
    ├── monitor_all.py           # 多 UP 主聚合入口（扫描 config/ 全部）
    ├── monitor.py               # 单 UP 主处理主脚本
    ├── get_up_videos.py         # B站 WBI 签名接口拉取视频列表
    ├── download_videos.py       # yt-dlp 音频下载（m4a）
    ├── transcribe_local.py      # faster-whisper 语音转文字
    ├── refiner.py               # DeepSeek API 精炼（三段式摘要）
    ├── db_writer.py             # DuckDB 写入（video_meta 表）
    ├── chroma_writer.py         # ChromaDB 写入（video_knowledge collection）
    ├── post_transcribe.py       # 转写后处理
    ├── qq_notify.py             # QQ Bot 推送通知
    ├── cookie_utils.py          # Netscape Cookie 解析
    ├── bili_api.py              # B站 API 封装
    ├── migrate_refined.py       # 精炼文件迁移脚本（已完成）
    └── migrate_history.py       # 历史文件迁移脚本
```

---

## 完整流程

```
[Cron 触发 · 每6小时 · bilibili-cron 容器]
    ↓
monitor_all.py（入口脚本）
    ├── 扫描 config/*.yaml（UP主配置）
    ├── 分批执行（MAX_CONCURRENT_TRANSCRIBE=2）
    └── 每个 UP 主调用 monitor.py
         ↓
    monitor.py（单个UP主处理）
         ├── 1. get_up_videos.py → WBI API 拉取视频列表
         ├── 2. download_videos.py → yt-dlp 下载 m4a
         ├── 3. transcribe_local.py → faster-whisper 转写 → txt
         ├── 4. refiner.py → DeepSeek API 精炼 → 三段式摘要
         ├── 5. db_writer.py → 写入 DuckDB（video_meta 表）
         ├── 6. chroma_writer.py → 写入 ChromaDB（video_knowledge）
         └── 7. qq_notify.py → QQ Bot 推送通知
```

---

## 双层 Checkpoint 机制

| 文件 | 含义 | 写入时机 |
|------|------|----------|
| `data/<name>_downloaded.txt` | 已下载待转写 | m4a 下载成功后立即写入 |
| `data/<name>_done_bvid.txt` | 转写完成 | 转写+精炼+入库全部成功后写入 |

**两层防呆**：即使转写失败/中断，BVID 仍留在 `downloaded.txt`，下次触发会重新转写，不会死锁。

---

## 快速开始

### 1. 配置 Cookie

从浏览器登录 B站后导出 Cookie（Netscape 格式），通过 `.env` 中的 `BILIBILI_COOKIE` 或挂载文件方式提供。

> ⚠️ SESSDATA 会过期。过期特征：`code=-352, message=风控校验失败`，重新登录导出即可。

### 2. 添加 UP 主配置

创建 `config/<任意名称>.yaml`：

```yaml
name: "是你的安佳佳呀"          # 下载目录名，可中文
uid: "410110370"               # B站空间 URL 中的数字
cookie_file: "~/.bilibili/cookie.txt"
download_root: "~/B站监控"

# QQ 通知（可选）
notify_target: "qq:65091C38C651B44BA071725FDF78A800"

# Whisper 转写设置
whisper_model: "medium"        # tiny/base/small/medium/large-v2/large-v3
whisper_device: "cuda"        # cuda 或 cpu
```

### 3. 运行（Docker）

```bash
# 完整流程（拉取→下载→转写→精炼→入库→通知）
docker compose run --rm bilibili-monitor

# 干跑模式（不实际执行）
docker compose run --rm bilibili-monitor python scripts/monitor_all.py --dry-run

# 指定某个 UP 主
docker compose run --rm bilibili-monitor python scripts/monitor_all.py --up 桃姐

# 只拉取元数据（不下载视频）
docker compose run --rm bilibili-monitor python scripts/monitor_all.py --metadata-only
```

### 4. 定时调度（NAS）

bilibili-cron 容器（仅 `nas` profile）每 6 小时自动触发：

```bash
# 启动定时调度
docker compose --profile nas up -d bilibili-cron

# 查看 cron 日志
docker logs -f bilibili-cron
```

cron 入口脚本 `cron_entry.sh` 包含：
- ChromaDB 健康检查（等待 chromadb 容器就绪）
- 执行 `docker compose run --rm bilibili-monitor`
- 日志轮转（10MB 阈值）

---

## 参数说明

### monitor.py

| 参数 | 说明 |
|------|------|
| `--dry-run` | 只查看新视频，不下载 |
| `--force` | 强制重新处理所有视频（忽略 done_bvid） |
| `--no-transcribe` | 跳过自动转写 |
| `--no-notify` | 跳过 QQ 通知 |

### monitor_all.py

| 参数 | 说明 |
|------|------|
| `--dry-run` | 只查看所有 UP 的新视频 |
| `--no-transcribe` | 跳过自动转写 |
| `--no-notify` | 跳过 QQ 通知 |
| `--up <name>` | 只运行指定 UP（模糊匹配） |

---

## 环境配置（.env）

```bash
# Whisper 转写（环境差异走 .env，不改代码）
WHISPER_MODEL=small          # GPU 环境用 large-v3，CPU 用 small
WHISPER_DEVICE=cpu           # cuda 或 cpu
COMPUTE_TYPE=int8            # GPU: float16, CPU: int8

# B站 Cookie
BILIBILI_COOKIE=xxx

# DeepSeek 精炼
REFINE_API_URL=http://10.168.165.50:3300/v1/chat/completions
REFINE_API_KEY=sk-xxx
REFINE_MODEL=deepseek-v4-pro

# ChromaDB（Docker 内部网络）
CHROMA_HOST=chromadb
CHROMA_PORT=8001

# QQ Bot
QQ_BOT_APPID=1903898888
QQ_BOT_TOKEN=xxx
```

---

## Docker 资源

```yaml
bilibili-monitor:
  mem_limit: 4g              # 转写峰值约 7-8G（含 faster-whisper）
  # 非常驻，run --rm 按需启动，跑完自动退出释放内存
```

**性能参考（faster-whisper small, CPU N150）：**
- 单条视频（8分钟音频）：约 3-5 分钟转写
- 每次 Cron（3 个新视频）：约 15-20 分钟

---

## 常见问题

### Cookie 失效（code=-352）

SESSDATA 过期，重新登录 B站后导出 Cookie 更新。

### 转写内存不足（OOM）

减小模型：`WHISPER_MODEL=small` 或 `base`，降低精度：`COMPUTE_TYPE=int8`。

### 并发禁忌

⚠️ 不要并发运行多个转写任务。`monitor_all.py` 内部 `MAX_CONCURRENT_TRANSCRIBE=2` 已做限流，不要手动并行启动多个容器。

### Checkpoint 文件名匹配

配置文件名到 checkpoint 文件的匹配**大小写不敏感**，去掉空格/下划线后统一小写比较。

| 配置文件 | downloaded | done_bvid |
|----------|------------|-----------|
| `an Jiajia.yaml` | `anjiajia_downloaded.txt` | `anjiajia_done_bvid.txt` |
| `3546912280021515.yaml` | `3546912280021515_downloaded.txt` | `3546912280021515_done_bvid.txt` |

---

**最后更新**：2026-05-25
**架构版本**：Phase 1 独立化改造后（无 Hermes 依赖）
