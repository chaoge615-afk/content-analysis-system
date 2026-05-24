#!/bin/bash
# 智能内容分析系统 - 端点健康检查脚本
# 用法：
#   ./scripts/test_endpoints.sh [base_url]
# 示例：
#   ./scripts/test_endpoints.sh http://localhost:3000
#   ./scripts/test_endpoints.sh http://nas-ip:3000

set -euo pipefail

BASE_URL="${1:-http://localhost:3000}"
PASS=0
FAIL=0

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

check_endpoint() {
    local name="$1"
    local url="$2"
    local method="${3:-GET}"
    local data="${4:-}"

    printf "  %-30s " "$name"

    if [ "$method" = "GET" ]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$url" --max-time 10 2>/dev/null || echo "000")
    else
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$url" --max-time 30 2>/dev/null || echo "000")
    fi

    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}[OK]${NC} (HTTP $HTTP_CODE)"
        ((PASS++))
    else
        echo -e "${RED}[FAIL]${NC} (HTTP $HTTP_CODE)"
        ((FAIL++))
    fi
}

echo "========================================"
echo "智能内容分析系统 - 健康检查"
echo "目标: $BASE_URL"
echo "========================================"
echo ""

echo "[前端]"
check_endpoint "首页" "$BASE_URL/"
echo ""

echo "[Router Agent]"
# 从前端端口通过 nginx 代理访问
check_endpoint "健康检查" "$BASE_URL/api/status"
check_endpoint "统一问答" "$BASE_URL/api/chat" "POST" '{"question":"测试"}'
echo ""

echo "[Text-to-SQL]"
check_endpoint "健康检查" "$BASE_URL/query" "POST" '{"question":"测试"}'
echo ""

echo "========================================"
echo -e "结果: ${GREEN}$PASS 通过${NC}, ${RED}$FAIL 失败${NC}"
echo "========================================"

if [ $FAIL -gt 0 ]; then
    exit 1
fi
