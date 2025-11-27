#!/bin/bash

# Warehouse Server 開發環境停止腳本（包含資料庫 + API）

# 顏色定義
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 取得相關路徑
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAREHOUSE_SERVER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DOCKER_DIR="$WAREHOUSE_SERVER_DIR/docker"
COMPOSE_FILE="$DOCKER_DIR/docker-compose.dev.yml"

# 檢查 docker-compose 檔案
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}❌ 錯誤：找不到 docker-compose 檔案：$COMPOSE_FILE${NC}"
    exit 1
fi

# 偵測 docker compose 指令
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}❌ 錯誤：未找到 docker-compose 或 docker compose 指令${NC}"
    exit 1
fi

echo -e "${BLUE}🛑 停止 Warehouse Server 開發環境...${NC}"
echo "📁 工作目錄: $DOCKER_DIR"
echo "📄 Compose 檔案: $COMPOSE_FILE"
echo ""

cd "$DOCKER_DIR" || exit 1

# 1. 停止 API
echo -e "${YELLOW}📦 停止 Warehouse API DEV...${NC}"
API_CONTAINER="warehouse-api-dev"
if docker ps --format '{{.Names}}' | grep -q "^${API_CONTAINER}$"; then
    if $DOCKER_COMPOSE -f docker-compose.dev.yml stop warehouse-api-dev; then
        echo -e "${GREEN}✅ Warehouse API DEV 已停止${NC}"
    else
        echo -e "${RED}❌ 錯誤：停止 Warehouse API DEV 失敗${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}ℹ️  Warehouse API DEV 未在執行${NC}"
fi
echo ""

# 2. 停止資料庫
echo -e "${YELLOW}📦 停止資料庫服務...${NC}"
if ! "$SCRIPT_DIR/stop_db.sh"; then
    echo -e "${RED}❌ 錯誤：停止資料庫服務失敗${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 已完成 Warehouse Server DEV 環境停止${NC}"
echo ""

