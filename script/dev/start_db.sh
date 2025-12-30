#!/bin/bash

# Warehouse Server 数据库启动脚本

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAREHOUSE_SERVER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DOCKER_DIR="$WAREHOUSE_SERVER_DIR/docker"
COMPOSE_FILE="$DOCKER_DIR/docker-compose.dev.yml"

# 检查 docker-compose 文件是否存在
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}❌ 错误：找不到 docker-compose 文件: $COMPOSE_FILE${NC}"
    exit 1
fi

# 检测 docker-compose 命令（支持 docker-compose 和 docker compose）
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}❌ 错误：未找到 docker-compose 或 docker compose 命令${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 启动 Warehouse Server 数据库...${NC}"
echo "📁 工作目录: $DOCKER_DIR"
echo "📄 Compose 文件: $COMPOSE_FILE"
echo ""

# 进入 docker 目录
cd "$DOCKER_DIR" || exit 1

# 检查并创建统一网络（如果不存在）
echo -e "${YELLOW}🌐 检查统一网络...${NC}"
UNIFIED_NETWORK="smart-warehouse-network-dev"
if ! docker network ls --format '{{.Name}}' | grep -q "^${UNIFIED_NETWORK}$"; then
    echo -e "${YELLOW}📦 创建统一网络 ${UNIFIED_NETWORK}...${NC}"
    if docker network create "${UNIFIED_NETWORK}"; then
        echo -e "${GREEN}✅ 统一网络已创建${NC}"
    else
        echo -e "${RED}❌ 错误：创建统一网络失败${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ 统一网络已存在${NC}"
fi
echo ""

# 检查并启动数据库
echo -e "${YELLOW}📦 检查数据库服务...${NC}"
CONTAINER_STATUS=$($DOCKER_COMPOSE -f docker-compose.dev.yml ps warehouse-mysql-dev 2>/dev/null | grep -E "(Up|running)" || echo "")

if [ -n "$CONTAINER_STATUS" ]; then
    echo -e "${GREEN}✅ MySQL Warehouse DEV 已在运行${NC}"
else
    echo -e "${YELLOW}📦 启动 MySQL Warehouse DEV...${NC}"
    
    # 启动数据库容器
    if ! $DOCKER_COMPOSE -f docker-compose.dev.yml up -d warehouse-mysql-dev; then
        echo -e "${RED}❌ 错误：启动 MySQL Warehouse DEV 失败${NC}"
        exit 1
    fi
    
    # 等待数据库就绪
    echo -e "${YELLOW}⏳ 等待数据库就绪...${NC}"
    sleep 5
    
    # 检查容器状态
    echo -e "${YELLOW}📊 检查服务状态...${NC}"
    $DOCKER_COMPOSE -f docker-compose.dev.yml ps warehouse-mysql-dev
    
    # 等待健康检查
    echo -e "${YELLOW}⏳ 等待健康检查...${NC}"
    MAX_WAIT=60
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        HEALTH=$($DOCKER_COMPOSE -f docker-compose.dev.yml ps --format json 2>/dev/null | grep -o '"Health":"healthy"' || echo "")
        if [ -n "$HEALTH" ]; then
            echo -e "${GREEN}✅ 数据库健康检查通过${NC}"
            break
        fi
        sleep 2
        WAIT_COUNT=$((WAIT_COUNT + 2))
        echo -n "."
    done
    echo ""
    
    # 从 docker-compose 文件读取连接信息
    DB_USER=$(grep "MYSQL_USER:" "$COMPOSE_FILE" | sed -E 's/.*MYSQL_USER:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
    DB_PASSWORD=$(grep "MYSQL_PASSWORD:" "$COMPOSE_FILE" | sed -E 's/.*MYSQL_PASSWORD:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
    DB_NAME=$(grep "MYSQL_DATABASE:" "$COMPOSE_FILE" | sed -E 's/.*MYSQL_DATABASE:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
    DB_PORT=$(grep -A 15 "warehouse-mysql-dev:" "$COMPOSE_FILE" | grep -E '^\s+-\s+"[0-9]+:[0-9]+"' | head -1 | sed -E 's/.*"([0-9]+):[0-9]+".*/\1/')
    
    echo ""
    echo -e "${GREEN}✅ MySQL Warehouse DEV 已启动${NC}"
    echo ""
    echo -e "${YELLOW}📊 数据库连接信息：${NC}"
    echo "   Host: localhost"
    echo "   Port: ${DB_PORT:-3307}"
    echo "   Database: ${DB_NAME:-smartwarehouse_warehouse_dev}"
    echo "     Username: ${DB_USER:-cowlin}"
    echo "     Password: ${DB_PASSWORD:-abc123}"
    echo ""
fi

echo -e "${GREEN}✅ 数据库服务已就绪${NC}"
echo ""

