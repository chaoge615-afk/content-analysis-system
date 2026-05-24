---
name: bilibili-monitor
description: 监控B站UP主更新，自动下载音频并触发转写，配合 QQ 机器人推送通知
version: 2.3.0
tags: [bilibili, monitor, download, QQ]
prerequisites:
  commands: [python3, yt-dlp, whisper]
  files:
    - ~/.bilibili/cookie.txt
    - bilibili-transcribe skill (已配置 venv)
---

# bilibili-monitor

监控 B站 UP 主新视频 → 下载音频 → 自动转写 → QQ 推送通知，完整流程一条命令。

## 目录结构

```
bilibili-monitor/
├── SKILL.md
├── config/                      # UP 主配置文件（一站一个）
│   ├── an Jiajia.yaml
│   └── 3546912280021515.yaml
├── data/                        # 已处理 BVID 记录（自动生成）
│   ├── anjiajia_done_bvid.txt   # 转写完成的 BV
│   └── 3546912280021515_done_bvid.txt
├── scripts/
│   ├── monitor.py               # 主脚本（单 UP）
│   ├── monitor_all.py           # 多 UP 聚合（扫描 config/ 全部）
│   ├── get_up_videos.py         # B站 WBI 签名接口
│   ├── download_videos.py       # yt-dlp 音频下载
│   ├── transcribe_local.py      # 本地 m4a 直接转写（不重新下载）
│   ├── qq_notify.py             # QQ 机器人通知
│   └── cookie_utils.py          # Netscape Cookie 解析
```

## 双层 Checkpoint 机制

| 文件 | 含义 | 写入时机 |
|------|------|----------|
| `data/<name>_downloaded.txt` | 已下载待转写 | 每个 m4a 下载成功后立即写入 |
| `data/<name>_done_bvid.txt` | 转写完成 | 转写成功后写入 |

**两层防呆**：即使转写失败/中断，BVID 仍留在 `downloaded.txt`，下次触发会重新转写，不会死锁。

**流程**：
1. 下载成功 → 写入 `downloaded.txt`
2. 转写触发前（两层预检）：
   - **monitor.py 预检**：`downloaded ∩ done_bvid` → 从 downloaded 移除
   - **transcribe_local.py 预检**：传入 `--done-bvid`，跳过已完成的 m4a 并删除
3. 转写成功 → 写入 `done_bvid.txt` + 从 `downloaded.txt` 移除
4. 转写失败 → BVID 留在 `downloaded.txt`（下次继续处理）

## 快速开始

### 1. 配置 Cookie

从浏览器登录 B站后导出 Cookie，保存到 `~/.bilibili/cookie.txt`（Netscape 格式）：

```
# Netscape HTTP Cookie File
.bilibili.com  TRUE  /  FALSE  1792889011  SESSDATA  xxx...
.bilibili.com  TRUE  /  FALSE  1792889011  bili_jct  yyy...
.bilibili.com  TRUE  /  FALSE  1792889011  DedeUserID  123456
```

> ⚠️ SESSDATA 会过期。过期特征：`code=-352, message=风控校验失败`，重新登录导出即可。
> ⚠️ SESSDATA 和 bili_jct 的 secure 字段（第 5 列）**必须为 `TRUE`**，否则报"缺少必需字段"。

### 2. 添加 UP 主配置

创建 `config/<任意名称>.yaml`：

```yaml
name: "是你的安佳佳呀"          # 下载目录名，可中文
uid: "410110370"               # B站空间 URL 中的数字
cookie_file: "~/.bilibili/cookie.txt"
download_root: "~/B站监控"

# QQ 通知（可选）
notify_target: "qq:65091C38C651B44BA071725FDF78A800"

# Whisper 转写
whisper_model: "medium"        # tiny/base/small/medium/large-v2/large-v3
whisper_device: "cuda"        # cuda 或 cpu
transcribe_skill_dir: "~/.hermes/skills/bilibili-transcribe"
```

### 3. 运行

```bash
cd ~/.hermes/skills/bilibili-monitor

# dry-run：查看有哪些新视频（不下载）
python3 scripts/monitor.py config/an\ Jiajia.yaml --dry-run

# 正式运行：下载 + 转写 + QQ 通知
python3 scripts/monitor.py config/an\ Jiajia.yaml
```

## 核心使用场景

### 场景 A：单独监控一个 UP 主

```bash
python3 scripts/monitor.py config/an\ Jiajia.yaml --dry-run          # 检查新视频
python3 scripts/monitor.py config/an\ Jiajia.yaml                    # 下载 + 转写 + 通知
python3 scripts/monitor.py config/an\ Jiajia.yaml --force            # 强制全量重跑（忽略 done_bvid）
```

### 场景 B：同时监控多个 UP 主

`monitor_all.py` 扫描整个 `config/` 目录，逐一运行全部配置：

```bash
python3 scripts/monitor_all.py --dry-run          # 全部 UP 一起 dry-run
python3 scripts/monitor_all.py                    # 全部 UP 下载 + 转写 + 通知
python3 scripts/monitor_all.py --up an             # 只运行指定 UP（模糊匹配）
```

### 场景 C：本地已有 m4a，只需要转写

```bash
. ~/.hermes/skills/bilibili-transcribe/.venv-bilibili-transcribe/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

python3 -u scripts/transcribe_local.py \
    "/home/chaoge/B站监控/恋爱教头桃姐" \
    --model-size medium --device cuda

# 参数：
#   --model-size   tiny/base/small/medium/large-v2/large-v3（默认 medium）
#   --device       cuda/cpu（默认 cuda）
#   --keep-audio   保留 m4a 文件（默认转写后自动删除）
#   --done-bvid    已完成 BVID 文件路径（自动跳过已转写的 m4a 并删除）
#   --min-duration 跳过小于此秒数的音频（默认 60）
```

## 完整流程

```
1. 加载 Cookie（检查必需字段：SESSDATA, bili_jct, DedeUserID）
2. 调用 B站 WBI 签名接口获取 UP 主视频列表
   - 新 UP（done_bvid=0）：全量拉取（最多 9999 条）
   - 已监控 UP：只拉第一页（30 条）
3. 过滤已处理视频（done_bvid + downloaded）
4. 下载新视频（只下音频 m4a）到 download_root/<name>/
5. 下载成功后立即写入 downloaded checkpoint
6. 调用 transcribe_local.py 转写 m4a → txt（m4a 同目录）
7. 转写成功后从 downloaded 移到 done_bvid checkpoint
8. [可选] QQ 推送新视频列表
```

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

## QQ 通知

发送条件：配置了 `notify_target: "qq:<openid>"` + 成功下载了视频 + 未用 `--no-notify`。

内容包含：UP 主名称 + 新视频数量 + 标题 + 发布时间 + 链接。

Bot 凭证已在 `.env` 中配置（AppID: 1903898888）。

## 定时监控

每 6 小时自动运行一次（0点、6点、12点、18点），监控 config/ 下全部 UP：

```bash
hermes cron create \
  --name "B站UP主监控" \
  --deliver qqbot \
  --enabled-toolsets terminal \
  "0 */6 * * *" \
  "bash -c 'cd /home/chaoge/.hermes/skills/bilibili-monitor && . ~/.hermes/skills/bilibili-transcribe/.venv-bilibili-transcribe/bin/activate && export HF_ENDPOINT=https://hf-mirror.com && python3 scripts/monitor_all.py 2>&1'"
```

> ⚠️ **必须使用 `--enabled-toolsets terminal` shell 直执行模式**，不可使用 `--skill bilibili-monitor`（skill agent 框架在 whisper 转写阶段会超时/静默失败）。

## Checkpoint 文件名匹配规则

配置文件名到 checkpoint 文件的匹配**大小写不敏感**：

| 配置文件 | 对应 downloaded | 对应 done_bvid |
|----------|----------------|----------------|
| `an Jiajia.yaml` | `anjiajia_downloaded.txt` | `anjiajia_done_bvid.txt` |
| `3546912280021515.yaml` | `3546912280021515_downloaded.txt` | `3546912280021515_done_bvid.txt` |

匹配逻辑：去掉空格/下划线后统一小写比较。

## 并发禁忌

⚠️ **禁止并发运行多个转写任务**。GPU 显存只够一个 Whisper medium 模型，并发会导致 OOM 或任务互相覆盖中断。

**错误做法**：
```bash
# ❌ 同时跑多个 transcribe_local.py — 会冲突
python3 scripts/transcribe_local.py "目录A" &
python3 scripts/transcribe_local.py "目录B" &
```

**正确做法**：统一走 `monitor_all.py`，它内部串行处理所有 UP，不会并发。
```bash
# ✅ 正确 — 全量串行
python3 scripts/monitor_all.py
```

## 常见问题

### Cookie 失效（code=-352）

SESSDATA 过期，重新登录 B站后导出 Cookie，更新 `~/.bilibili/cookie.txt`。

### Cookie 缺少必需字段（即使文件包含这些字段）

SESSDATA 和 bili_jct 的 secure flag（第 5 列）**必须为 `TRUE`**。检查：
```bash
grep -E "SESSDATA|bili_jct" ~/.bilibili/cookie.txt
```
第 5 列应为 `TRUE`。

### 下载失败（No module named yt_dlp）

使用 bilibili-transcribe 的 venv，不依赖系统 Python。确认 venv 存在：
```bash
ls ~/.hermes/skills/bilibili-transcribe/.venv-bilibili-transcribe/bin/python
```

### 转写显存不够（CUDA OOM）

减小模型：`--model-size small`，或换 CPU：`--device cpu`。

### 只拉取到 30 个视频（首次部署必检）

`monitor.py` 和 `monitor_all.py` 第 188 行 hardcoded `max_count=30`，导致超过 30 个视频的 UP 只下载第一页。

**修复方法（首次部署时执行一次即可）**：
```bash
sed -i 's/max_count=30/max_count=9999/' scripts/monitor.py scripts/monitor_all.py
```

### done_bvid 有记录但无 txt 文件（转写静默失败）

诊断：
```bash
done_count=$(wc -l < ~/.hermes/skills/bilibili-monitor/data/<name>_done_bvid.txt)
txt_count=$(find ~/B站监控/<name>/ -name "*.txt" | wc -l)
echo "done_bvid: $done_count, txt: $txt_count"
```

处理：手动对那个目录跑 `transcribe_local.py`，或用 `--force` 重新下载+转写。

### downloaded.txt 有记录但 done_bvid.txt 没有更新（死锁）

**v2.3+ 已修复此问题**：转写触发前有两层预检，即使转写中断，BVID 仍留在 `downloaded.txt`，下次运行会重新触发转写。

如果仍在旧版本（v2.2），诊断和修复方法同上（手动将 BVID 从 downloaded 移到 done_bvid）。

### 进程被中断/超时

`transcribe_local.py` 每次循环重新加载 Whisper 模型（~5GB），WSL 下 SIGALRM 不稳定，长音频（>8分钟）可能被系统超时杀掉。

处理：重新运行 `monitor_all.py`，已转写的会自动跳过（有 txt 就不重复转写）。

### 手动触发转写后任务消失（被覆盖）

原因：在同一个终端里又执行了新的 `monitor.py` 或 `transcribe_local.py` 命令，把前一个任务冲掉了（不是被系统 kill，是被新的前台进程替换了）。

处理：使用 `monitor_all.py` 统一运行，不分别触发单个 UP 的转写任务。如果需要后台运行，用 `background=true` 参数（见下方"定时监控"章节）。

### 中断后如何恢复（完整步骤）

当 `monitor_all.py` 或 `monitor.py` 被中断后，按以下顺序检查和恢复：

**1. 确认中断原因**
```bash
# dmesg 无 OOM/kill 记录 = 手动中断（Ctrl+C），不是系统杀死
dmesg | grep -E "killed|oom|CUDA"
```

**2. 找出未转写的 m4a**
```bash
find ~/B站监控/<UP主目录>/ -name "*.m4a"
```
有输出说明有残留待转写。

**3. 检查 downloaded checkpoint 是否有多余 BVID**
```bash
cat ~/.hermes/skills/bilibili-monitor/data/<name>_downloaded.txt
```
如果 downloaded.txt 里有 BVID 但对应的 .m4a 已不存在（被中断删除了？），需要手动清理：
```bash
# 删除 downloaded 中多余的 BVID（手动编辑或用 Python）
```

**4. 后台重新触发转写（推荐）**
不要在前台跑，用 `background:true` 参数避免前台命令互相抢占：
```
terminal(background=true, command="...transcribe_local.py ...", timeout=600)
```
可以同时跑多个 UP 主的转写，互不阻塞：
- `transcribe_local.py <恋爱教头桃姐目录>` → 后台
- `transcribe_local.py <是你的安佳佳呀目录>` → 后台
- `monitor.py config/夹性学姐在这.yaml` → 后台（含下载）

**5. 用 process 工具追踪进度**
```bash
hermes process list   # 只显示当前会话启动的进程
```
注意：用户自己启动的后台任务（如 `nohup ... &`）不在列表里，仍需用 `find` 查文件验证。

**6. 验证转写完成**
转写成功后 .m4a 会自动删除，目录里只剩 .txt 文件。转写失败的特征是 .txt 只有 1 字节或极小（<100 字节）。

### 漏检后如何补扫

```bash
# 单个 UP 补扫
python3 scripts/monitor.py config/3546912280021515.yaml --force

# 全部 UP 补扫
python3 scripts/monitor_all.py --force
```

> ⚠️ `--force` 会忽略 done_bvid，下载并转写全部历史视频（最多 9999 条），确认只会触发一次。

## Cron 可靠性

### 检查 Cron 是否正常运行

Cron 输出在 `~/.hermes/cron/output/<job_id>/`，每个文件对应一次运行。检查运行间隔：
```python
from datetime import datetime
import os
job_id = "your_job_id"
base = f"/home/chaoge/.hermes/cron/output/{job_id}"
files = sorted(os.listdir(base))
times = [datetime.fromtimestamp(os.path.getmtime(os.path.join(base, f))) for f in files]
for i in range(1, len(times)):
    gap_h = (times[i] - times[i-1]).total_seconds() / 3600
    label = "⚠️ 异常" if gap_h > 7 else "✅"
    print(f"  {files[i-1][-20:-3]} → {files[i][-20:-3]}  间隔: {gap_h:.1f}h  {label}")
```

### Cron 长时间不运行的常见原因

- **WSL 休眠/关机**：WSL 关机期间 cron 不执行，开机后不会补跑
- **Hermes Gateway 重启**：Gateway 进程重启期间错过触发
- **系统时区变化**：系统时区必须是 `Asia/Shanghai`（`timedatectl set-timezone Asia/Shanghai`）

### session 文件只有 Prompt 无执行结果（cron 静默失败）

这是使用 `--skill bilibili-monitor` 的已知问题。特征：session 文件大小约 9508 字节，内容只有 Prompt 模板。

**修复**：重建 cron job，改用 `--enabled-toolsets terminal`（见上方"定时监控"章节）。
