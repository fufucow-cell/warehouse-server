#!/bin/bash

# Warehouse Server 数据库停止脚本

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

echo -e "${BLUE}🛑 停止 Warehouse Server 数据库...${NC}"
echo "📁 工作目录: $DOCKER_DIR"
echo "📄 Compose 文件: $COMPOSE_FILE"
echo ""

# 进入 docker 目录
cd "$DOCKER_DIR" || exit 1

# 停止数据库
echo -e "${YELLOW}📦 停止 MySQL Warehouse DEV...${NC}"
CONTAINER_NAME="warehouse-mysql-dev"
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        if $DOCKER_COMPOSE -f docker-compose.dev.yml stop warehouse-mysql-dev; then
            echo -e "${GREEN}✅ MySQL Warehouse DEV 已停止${NC}"
    else
            echo -e "${RED}❌ 错误：停止 MySQL Warehouse DEV 失败${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}ℹ️  MySQL Warehouse DEV 未运行${NC}"
fi

echo ""
echo -e "${GREEN}✅ 完成！${NC}"

