#!/bin/sh
# bilibili-monitor 定时任务入口脚本
# 由 docker-compose 中的 bilibili-cron 服务调用
# 每 6 小时运行一次 bilibili-monitor

set -eu

PROJECT_DIR="/project"
LOG_FILE="/var/log/bilibili-cron.log"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "========================================" >> "$LOG_FILE"
echo "[$TIMESTAMP] 开始执行 bilibili-monitor" >> "$LOG_FILE"

# 检查 chromadb 是否运行
if ! docker compose -f "$PROJECT_DIR/docker-compose.yml" --profile nas ps 2>/dev/null | grep -q "chromadb.*Up\|chromadb.*running"; then
    echo "[$TIMESTAMP] WARNING: chromadb 未运行，尝试启动..." >> "$LOG_FILE"
    docker compose -f "$PROJECT_DIR/docker-compose.yml" --profile nas up -d chromadb >> "$LOG_FILE" 2>&1
    sleep 15
fi

# 执行 bilibili-monitor
echo "[$TIMESTAMP] 执行 docker compose run bilibili-monitor..." >> "$LOG_FILE"
docker compose -f "$PROJECT_DIR/docker-compose.yml" --profile nas run --rm bilibili-monitor >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] SUCCESS: bilibili-monitor 执行完成 (exit: $EXIT_CODE)" >> "$LOG_FILE"
else
    echo "[$TIMESTAMP] ERROR: bilibili-monitor 执行失败 (exit: $EXIT_CODE)" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"

# 日志轮转：超过 10MB 则保留最后 5000 行
if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)" -gt 10485760 ]; then
    tail -n 5000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    echo "[$TIMESTAMP] 日志已轮转" >> "$LOG_FILE"
fi

exit $EXIT_CODE
