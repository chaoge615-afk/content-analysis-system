#!/bin/bash
# bilibili-monitor 定时任务脚本
# 用于 cron 调度，每 6 小时运行一次
#
# 安装方式（在 NAS 或服务器上）：
#   crontab -e
#   # 添加以下行（每 6 小时运行一次）：
#   0 */6 * * * /path/to/ai项目/scripts/cron_monitor.sh >> /path/to/ai项目/logs/cron.log 2>&1

set -euo pipefail

# 项目根目录（相对于脚本位置）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 日志目录
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# 时间戳
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "========================================" >> "$LOG_DIR/cron.log"
echo "[$TIMESTAMP] 开始执行 bilibili-monitor" >> "$LOG_DIR/cron.log"
echo "========================================" >> "$LOG_DIR/cron.log"

# 切换到项目目录
cd "$PROJECT_DIR"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "[$TIMESTAMP] ERROR: Docker 未运行" >> "$LOG_DIR/cron.log"
    exit 1
fi

# 检查必要服务是否运行
if ! docker compose --profile nas ps | grep -q "chromadb.*Up"; then
    echo "[$TIMESTAMP] WARNING: chromadb 未运行，尝试启动..." >> "$LOG_DIR/cron.log"
    docker compose --profile nas up -d chromadb
    sleep 10
fi

# 执行 bilibili-monitor
echo "[$TIMESTAMP] 执行 docker compose run..." >> "$LOG_DIR/cron.log"
docker compose --profile nas run --rm bilibili-monitor >> "$LOG_DIR/monitor.log" 2>&1

EXIT_CODE=$?

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] SUCCESS: bilibili-monitor 执行完成" >> "$LOG_DIR/cron.log"
else
    echo "[$TIMESTAMP] ERROR: bilibili-monitor 执行失败 (exit code: $EXIT_CODE)" >> "$LOG_DIR/cron.log"
fi

echo "" >> "$LOG_DIR/cron.log"

exit $EXIT_CODE
