#!/bin/bash
# 后台加载知识库脚本
# 使用: ./scripts/load_knowledge_bg.sh

set -euo pipefail

# 获取脚本所在目录，然后得到项目根目录
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/..")

cd "$PROJECT_ROOT"

# 环境检查
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境目录 venv/ 不存在，请先创建虚拟环境并安装依赖"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "错误: .env 文件不存在，请复制 .env.example 为 .env 并配置API密钥"
    exit 1
fi

if [ ! -d "knowledge" ]; then
    echo "警告: knowledge/ 目录不存在，创建空目录"
    mkdir -p knowledge
fi

# 创建日志目录
mkdir -p logs

# 激活虚拟环境
source venv/bin/activate

# 生成日志文件名
LOG_FILE="logs/load_$(date +%Y%m%d_%H%M%S).log"

echo "Starting background knowledge loading..."
echo "Log file: $LOG_FILE"

# 启动后台进程
nohup python load_cli.py >> "$LOG_FILE" 2>&1 &

# 保存PID
PID=$!
echo $PID > logs/last_load.pid

echo "Process started in background with PID: $PID"
echo "To view progress: tail -f $LOG_FILE"
echo "To check process status: ps -p $PID"
