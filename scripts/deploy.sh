#!/bin/bash
# 智能内容分析系统 - 部署脚本
# 用法：
#   ./scripts/deploy.sh dev    # 开发环境
#   ./scripts/deploy.sh nas    # 生产环境（NAS）

set -euo pipefail

PROFILE="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "智能内容分析系统 - 部署脚本"
echo "环境: $PROFILE"
echo "========================================"

cd "$PROJECT_DIR"

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "ERROR: .env 文件不存在"
    echo "请复制 .env.example 为 .env 并填入 API 密钥："
    echo "  cp .env.example .env"
    echo "  vim .env"
    exit 1
fi

# 检查必要的环境变量
source .env
MISSING_VARS=()

if [ -z "${MINIMAX_API_KEY:-}" ]; then
    MISSING_VARS+=("MINIMAX_API_KEY")
fi
if [ -z "${SILICONFLOW_API_KEY:-}" ]; then
    MISSING_VARS+=("SILICONFLOW_API_KEY")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "ERROR: 以下环境变量未配置："
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

echo "环境变量检查通过"
echo ""

# 构建并启动服务
echo "构建 Docker 镜像..."
docker compose --profile "$PROFILE" build

echo ""
echo "启动服务..."
docker compose --profile "$PROFILE" up -d

echo ""
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo ""
echo "服务状态："
docker compose --profile "$PROFILE" ps

echo ""
echo "========================================"
echo "部署完成！"
echo ""
echo "访问地址："
if [ "$PROFILE" = "dev" ]; then
    echo "  前端:      http://localhost:3000"
    echo "  Router:    http://localhost:8000"
    echo "  SQL API:   http://localhost:8010"
    echo "  RAG API:   http://localhost:8090"
else
    echo "  前端:      http://<NAS-IP>:3000"
    echo "  Router:    http://<NAS-IP>:8000"
    echo "  SQL API:   http://<NAS-IP>:8010"
    echo "  RAG API:   http://<NAS-IP>:8090"
fi
echo ""
echo "运行 bilibili-monitor（按需）："
echo "  docker compose --profile $PROFILE run --rm bilibili-monitor"
echo ""
echo "查看日志："
echo "  docker compose --profile $PROFILE logs -f"
echo "========================================"
