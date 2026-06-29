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

# GPU 实测：仅 dev profile 下才检测，决定是否追加 gpu profile（gpu-service）
# 用 --gpus all 启动最小容器，容器 init 阶段即校验 NVIDIA 直通
#   有 GPU 直通（4060 开发机）→ init 成功，返回 0
#   无 GPU / 无 toolkit / WSL 无适配器（办公机）→ init 失败，返回非 0
PROFILES="$PROFILE"
if [ "$PROFILE" = "dev" ]; then
    echo "检测 NVIDIA GPU..."
    if docker run --rm --gpus all alpine:latest echo gpu-ok >/dev/null 2>&1; then
        PROFILES="$PROFILE gpu"
        echo "✓ 检测到 NVIDIA GPU，包含 gpu-service"
    else
        echo "✗ 未检测到可用 GPU，跳过 gpu-service（转写将回退到云ASR/CPU）"
    fi
    echo ""
fi

# 构建并启动服务
echo "构建 Docker 镜像..."
docker compose --profile $PROFILES build

echo ""
echo "启动服务..."
docker compose --profile $PROFILES up -d

echo ""
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo ""
echo "服务状态："
docker compose --profile $PROFILES ps

echo ""
echo "========================================"
echo "部署完成！"
echo ""
echo "访问地址："
if [ "$PROFILE" = "dev" ]; then
    echo "  前端:      http://localhost:80"
    echo "  Router:    http://localhost:8000"
    echo "  SQL API:   http://localhost:8010"
    echo "  RAG API:   http://localhost:8090"
else
    echo "  前端:      http://<NAS-IP>:80"
    echo "  Router:    http://<NAS-IP>:8000"
    echo "  SQL API:   http://<NAS-IP>:8010"
    echo "  RAG API:   http://<NAS-IP>:8090"
fi
echo ""
echo "运行 bilibili-monitor（按需）："
echo "  docker compose --profile $PROFILES run --rm bilibili-monitor"
echo ""
echo "查看日志："
echo "  docker compose --profile $PROFILES logs -f"
echo ""

# ==============================
# 自动清理废弃镜像 + 构建缓存
# ==============================
# 仅清悬空镜像（已无标签的旧版本镜像，重建后被 latest 顶替下来的）。
# 绝不用 `image prune -a`：那会连 bilibili-monitor(Exited)/gpu-service(Created)
# 这类按需但无运行容器的镜像一起删掉。
echo "清理废弃镜像和构建缓存..."
docker image prune -f || echo "[WARN] 镜像清理失败（不影响已部署服务）"
# 构建缓存随时可重新生成，可全清（配合上方 image prune -f 清悬空旧版）。
# 用 || true 兜底，避免 set -e 下清理失败导致整个部署脚本非零退出。
docker builder prune -a -f || echo "[WARN] 构建缓存清理失败（不影响已部署服务）"
echo "========================================"
