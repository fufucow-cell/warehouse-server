#!/bin/bash

# Warehouse Server 開發環境啟動腳本（包含資料庫 + API）

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

echo -e "${BLUE}🚀 啟動 Warehouse Server 開發環境...${NC}"
echo "📁 工作目錄: $DOCKER_DIR"
echo "📄 Compose 檔案: $COMPOSE_FILE"
echo ""

# 1. 啟動資料庫
echo -e "${YELLOW}📦 啟動資料庫服務...${NC}"
if ! "$SCRIPT_DIR/start_db.sh"; then
    echo -e "${RED}❌ 錯誤：啟動資料庫服務失敗${NC}"
    exit 1
fi
echo ""

# 2. 啟動 API
cd "$DOCKER_DIR" || exit 1
echo -e "${YELLOW}🔍 檢查 Warehouse API 服務...${NC}"
API_STATUS=$($DOCKER_COMPOSE -f docker-compose.dev.yml ps warehouse-api-dev 2>/dev/null | grep -E "(Up|running)" || echo "")

if [ -n "$API_STATUS" ]; then
    echo -e "${GREEN}✅ Warehouse API DEV 已在執行${NC}"
else
    echo -e "${YELLOW}📦 啟動 Warehouse API DEV...${NC}"
    if ! $DOCKER_COMPOSE -f docker-compose.dev.yml up -d warehouse-api-dev; then
        echo -e "${RED}❌ 錯誤：啟動 Warehouse API DEV 失敗${NC}"
        exit 1
    fi
    echo -e "${YELLOW}⏳ 等候服務啟動...${NC}"
    sleep 5
fi
echo ""

# 3. 顯示服務狀態
echo -e "${YELLOW}📊 服務狀態：${NC}"
$DOCKER_COMPOSE -f docker-compose.dev.yml ps warehouse-mysql-dev warehouse-api-dev
echo ""

# 4. 顯示連線資訊
DB_USER=$(grep "MYSQL_USER:" "$COMPOSE_FILE" | sed -E 's/.*MYSQL_USER:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
DB_PASSWORD=$(grep "MYSQL_PASSWORD:" "$COMPOSE_FILE" | sed -E 's/.*MYSQL_PASSWORD:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
DB_NAME=$(grep "MYSQL_DATABASE:" "$COMPOSE_FILE" | sed -E 's/.*MYSQL_DATABASE:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
DB_PORT=$(grep -A 15 "warehouse-mysql-dev:" "$COMPOSE_FILE" | grep -E '^\s+-\s+"[0-9]+:[0-9]+"' | head -1 | sed -E 's/.*"([0-9]+):[0-9]+".*/\1/')

echo -e "${GREEN}✅ Warehouse Server DEV 環境已啟動${NC}"
echo ""
echo -e "${YELLOW}📡 API：${NC}"
echo "   http://localhost:8003"
echo "   http://localhost:8003/docs"
echo ""
echo -e "${YELLOW}🗄️  Database：${NC}"
echo "   Host: localhost"
echo "   Port: ${DB_PORT:-3307}"
echo "   Database: ${DB_NAME:-smartwarehouse_warehouse_dev}"
echo "   Username: ${DB_USER:-cowlin}"
echo "   Password: ${DB_PASSWORD:-abc123}"
echo ""

