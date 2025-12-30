#!/bin/bash

# 数据库初始化脚本 - 使用本地 MySQL 客户端
# 需要通过本地 MySQL 客户端连接到 Docker 容器中的 MySQL

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
DOCKER_COMPOSE_FILE="$DOCKER_DIR/docker-compose.dev.yml"

echo -e "${BLUE}🔧 使用本地 MySQL 客户端初始化数据库...${NC}"
echo ""

# 检查 mysql 命令是否可用
if ! command -v mysql &> /dev/null; then
    echo -e "${RED}❌ 错误：未找到 mysql 客户端${NC}"
    echo ""
    echo -e "${YELLOW}💡 安装 MySQL 客户端：${NC}"
    echo "   macOS: brew install mysql-client"
    echo "   Ubuntu/Debian: sudo apt-get install mysql-client"
    exit 1
fi

echo -e "${GREEN}✅ 找到 MySQL 客户端${NC}"
echo ""

# 从 docker-compose 文件读取数据库配置
echo -e "${YELLOW}📄 读取 docker-compose.dev.yml 配置...${NC}"

# 提取配置的函数
extract_value() {
    local key=$1
    local file=$2
    local line=$(grep -A 10 "warehouse-mysql-dev:" "$file" | grep "${key}:" | head -1)
    if [ -n "$line" ]; then
        echo "$line" | sed -E "s/.*${key}:[[:space:]]*([^[:space:]]+).*/\1/" | tr -d '"' | tr -d "'"
    fi
}

DB_USER=$(extract_value "MYSQL_USER" "$DOCKER_COMPOSE_FILE")
DB_PASSWORD=$(extract_value "MYSQL_PASSWORD" "$DOCKER_COMPOSE_FILE")
DB_NAME=$(extract_value "MYSQL_DATABASE" "$DOCKER_COMPOSE_FILE")

# 从 docker-compose 文件读取端口
PORT_LINE=$(grep -A 15 "warehouse-mysql-dev:" "$DOCKER_COMPOSE_FILE" | grep -E '^\s+-\s+"[0-9]+:[0-9]+"' | head -1)
if [ -n "$PORT_LINE" ]; then
    DB_PORT=$(echo "$PORT_LINE" | sed -E 's/.*"([0-9]+):[0-9]+".*/\1/')
fi

# 默认值
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-3307}

# 验证配置
if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ] || [ -z "$DB_NAME" ]; then
    echo -e "${RED}❌ 错误：无法从 docker-compose.dev.yml 中读取完整的数据库配置${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 成功读取配置${NC}"
echo ""
echo -e "${YELLOW}📊 连接信息：${NC}"
echo "   Host: ${DB_HOST}"
echo "   Port: ${DB_PORT}"
echo "   Database: ${DB_NAME}"
echo "   Username: ${DB_USER}"
echo ""

# 检查容器是否在运行
CONTAINER_NAME="warehouse-mysql-dev"
echo -e "${YELLOW}🔍 检查数据库容器...${NC}"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}❌ 错误：MySQL 容器未运行${NC}"
    echo ""
    echo -e "${YELLOW}💡 请先启动数据库容器：${NC}"
    echo "   cd $WAREHOUSE_SERVER_DIR/docker && docker-compose -f docker-compose.dev.yml up -d warehouse-mysql-dev"
    exit 1
fi

echo -e "${GREEN}✅ 容器正在运行${NC}"
echo ""

# 检查数据库连接
echo -e "${YELLOW}🔍 检查数据库连接...${NC}"

if mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 数据库连接成功${NC}"
else
    echo -e "${RED}❌ 无法连接到数据库${NC}"
    echo ""
    echo -e "${YELLOW}💡 请确保：${NC}"
    echo "   1. MySQL 容器正在运行"
    echo "   2. 端口映射正确（外部端口应为 ${DB_PORT}）"
    echo "   3. 等待容器完全启动（MySQL 需要一些时间初始化）"
    exit 1
fi

echo ""

# 初始化数据库表（使用 migrations 目录中的 SQL 文件）
echo -e "${BLUE}📦 创建数据库表结构...${NC}"

# 获取 migrations 目录路径
MIGRATIONS_DIR="$WAREHOUSE_SERVER_DIR/migrations"

# 检查目录是否存在
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo -e "${RED}❌ 错误：找不到 migrations 目录: $MIGRATIONS_DIR${NC}"
    exit 1
fi

# 查找所有 .sql 文件并按文件名排序
SQL_FILES=($(find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.sql" -type f -exec basename {} \; | sort))

if [ ${#SQL_FILES[@]} -eq 0 ]; then
    echo -e "${RED}❌ 错误：在 migrations 目录中找不到任何 .sql 文件${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 发现 ${#SQL_FILES[@]} 个 SQL 文件，将按以下顺序执行：${NC}"
for i in "${!SQL_FILES[@]}"; do
    echo -e "   $((i+1)). ${SQL_FILES[$i]}"
done
echo ""

# 按顺序执行每个 SQL 文件
SQL_EXIT_CODE=0
for sql_file in "${SQL_FILES[@]}"; do
    sql_path="$MIGRATIONS_DIR/$sql_file"
    
    if [ ! -f "$sql_path" ]; then
        echo -e "${RED}❌ 错误：找不到 SQL 文件: $sql_path${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}   ▶ 执行: $sql_file${NC}"
    
    # 使用本地 MySQL 客户端执行
    mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < "$sql_path"
    SQL_EXIT_CODE=$?
    
    if [ $SQL_EXIT_CODE -ne 0 ]; then
        echo -e "${RED}❌ 执行 $sql_file 失败${NC}"
        exit 1
    else
        echo -e "${GREEN}   ✅ $sql_file 执行成功${NC}"
    fi
done

# 检查 SQL 执行结果
if [ $SQL_EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 数据库初始化完成！${NC}"
    echo ""
    echo -e "${YELLOW}📋 已创建的表：${NC}"
    mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SHOW TABLES;" 2>/dev/null || echo "   (表列表获取失败)"
    echo ""
else
    echo ""
    echo -e "${RED}❌ 数据库初始化失败${NC}"
    exit 1
fi

