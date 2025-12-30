#!/bin/bash

# 数据库初始化脚本 - DEV 环境专用
# 从 docker-compose.dev.yml 读取配置并初始化数据库

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

echo -e "${BLUE}🔧 初始化 Warehouse Server DEV 環境的數據庫...${NC}"
echo ""

# 检查 docker-compose 文件是否存在
if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    echo -e "${RED}❌ 錯誤：找不到 docker-compose 文件: $DOCKER_COMPOSE_FILE${NC}"
    exit 1
fi

# 从 docker-compose 文件读取数据库配置
echo -e "${YELLOW}📄 讀取 docker-compose.dev.yml 配置...${NC}"

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
    echo -e "${RED}❌ 錯誤：無法從 docker-compose.dev.yml 中讀取完整的數據庫配置${NC}"
    echo "請檢查文件: $DOCKER_COMPOSE_FILE"
    echo "已讀取的配置:"
    echo "  DB_USER: ${DB_USER:-未找到}"
    echo "  DB_PASSWORD: ${DB_PASSWORD:+已設置}"
    echo "  DB_NAME: ${DB_NAME:-未找到}"
    exit 1
fi

echo -e "${GREEN}✅ 成功讀取配置${NC}"
echo ""
echo -e "${YELLOW}📊 連接資訊：${NC}"
echo "   Host: ${DB_HOST}"
echo "   Port: ${DB_PORT}"
echo "   Database: ${DB_NAME}"
echo "   Username: ${DB_USER}"
echo "   Password: ${DB_PASSWORD}"
echo ""

# 檢查容器是否在運行
CONTAINER_NAME="warehouse-mysql-dev"
echo -e "${YELLOW}🔍 檢查數據庫容器...${NC}"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}❌ 錯誤：MySQL 容器未運行${NC}"
    echo ""
    echo -e "${YELLOW}💡 請先啟動數據庫容器：${NC}"
    # 检测 docker-compose 命令
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
    echo "   cd $WAREHOUSE_SERVER_DIR/docker && $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml up -d warehouse-mysql-dev"
    exit 1
fi

echo -e "${GREEN}✅ 容器正在運行${NC}"

# 等待容器就绪
CONTAINER_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null)
if [ "$CONTAINER_HEALTH" = "starting" ]; then
    echo -e "${YELLOW}⏳ 等待容器就緒...${NC}"
    MAX_WAIT=30
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        CONTAINER_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null)
        if [ "$CONTAINER_HEALTH" = "healthy" ] || [ "$CONTAINER_HEALTH" = "" ]; then
            break
        fi
        sleep 2
        WAIT_COUNT=$((WAIT_COUNT + 2))
        echo -n "."
    done
    echo ""
fi

# 檢查數據庫連接
echo -e "${YELLOW}🔍 檢查數據庫連接...${NC}"

# 尝试两种连接方式：
# 1. 优先使用 docker exec（更可靠，不需要本地安装 psql）
# 2. 如果失败，尝试从容器外部连接（通过端口映射）

USE_DOCKER_EXEC=false
CONNECTION_SUCCESS=false

# 方式1：优先使用 docker exec（推荐，更可靠）
if docker exec ${CONTAINER_NAME} mysql -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SELECT 1;" > /dev/null 2>&1; then
    USE_DOCKER_EXEC=true
    CONNECTION_SUCCESS=true
    echo -e "${GREEN}✅ 數據庫連接成功（使用容器內部連接）${NC}"
else
    # 方式2：尝试从外部连接（需要本地安装 mysql）
    if command -v mysql &> /dev/null; then
        echo -e "${YELLOW}   容器內部連接失敗，嘗試外部連接...${NC}"
        if mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SELECT 1;" > /dev/null 2>&1; then
            USE_DOCKER_EXEC=false
            CONNECTION_SUCCESS=true
            echo -e "${GREEN}✅ 數據庫連接成功（使用外部連接）${NC}"
        fi
    else
        echo -e "${YELLOW}   mysql 未安裝，無法使用外部連接${NC}"
    fi
fi

if [ "$CONNECTION_SUCCESS" = false ]; then
    # 检查是否是数据库不存在的问题（MySQL 容器启动时会自动创建数据库，这里主要是检查连接）
    echo -e "${YELLOW}🔍 檢查數據庫連接狀態...${NC}"
    # MySQL 容器启动时会自动创建数据库，如果连接失败可能是其他原因
    echo -e "${RED}❌ 無法連接到數據庫${NC}"
    echo ""
    echo -e "${YELLOW}🔍 診斷資訊：${NC}"
    echo "   容器狀態: $(docker inspect --format='{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo '未找到')"
    echo "   連接參數:"
    echo "     Host: ${DB_HOST}"
    echo "     Port: ${DB_PORT}"
    echo "     Database: ${DB_NAME}"
    echo "     Username: ${DB_USER}"
    echo ""
    echo -e "${YELLOW}💡 測試連接命令：${NC}"
    echo "   外部連接: mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e 'SELECT 1;'"
    echo "   容器內部: docker exec ${CONTAINER_NAME} mysql -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e 'SELECT 1;'"
    echo ""
    echo -e "${YELLOW}💡 可能的解決方案：${NC}"
    echo "   1. 確認容器正在運行: docker ps | grep ${CONTAINER_NAME}"
    echo "   2. 檢查容器日誌: docker logs ${CONTAINER_NAME}"
    echo "   3. 檢查端口是否正確: lsof -i :${DB_PORT}"
    echo "   4. 等待容器完全啟動（MySQL 需要一些時間初始化）"
    exit 1
fi

echo -e "${GREEN}✅ 數據庫連接成功${NC}"
echo ""

# 初始化數據庫表（使用 migrations 目錄中的 SQL 文件）
echo -e "${BLUE}📦 創建數據庫表結構（全新數據庫）...${NC}"

# 获取 migrations 目录路径
MIGRATIONS_DIR="$WAREHOUSE_SERVER_DIR/migrations"

# 检查目录是否存在
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo -e "${RED}❌ 錯誤：找不到 migrations 目錄: $MIGRATIONS_DIR${NC}"
    exit 1
fi

# 查找所有 .sql 文件并按文件名排序（确保按顺序执行）
SQL_FILES=($(find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.sql" -type f -exec basename {} \; | sort))

if [ ${#SQL_FILES[@]} -eq 0 ]; then
    echo -e "${RED}❌ 錯誤：在 migrations 目錄中找不到任何 .sql 文件${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 發現 ${#SQL_FILES[@]} 個 SQL 文件，將按以下順序執行：${NC}"
for i in "${!SQL_FILES[@]}"; do
    echo -e "   $((i+1)). ${SQL_FILES[$i]}"
done
echo ""

# 按顺序执行每个 SQL 文件
SQL_EXIT_CODE=0
for sql_file in "${SQL_FILES[@]}"; do
    sql_path="$MIGRATIONS_DIR/$sql_file"
    
    if [ ! -f "$sql_path" ]; then
        echo -e "${RED}❌ 錯誤：找不到 SQL 文件: $sql_path${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}   ▶ 執行: $sql_file${NC}"
    
    # 根据连接方式选择执行命令
    if [ "$USE_DOCKER_EXEC" = true ]; then
        docker exec -i ${CONTAINER_NAME} mysql -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < "$sql_path"
        SQL_EXIT_CODE=$?
    else
        mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < "$sql_path"
        SQL_EXIT_CODE=$?
    fi
    
    if [ $SQL_EXIT_CODE -ne 0 ]; then
        echo -e "${RED}❌ 執行 $sql_file 失敗${NC}"
        exit 1
    else
        echo -e "${GREEN}   ✅ $sql_file 執行成功${NC}"
    fi
done

# 检查 SQL 执行结果
if [ $SQL_EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ DEV 環境數據庫初始化完成！${NC}"
    echo ""
    echo -e "${YELLOW}📋 已創建的表：${NC}"
    if [ "$USE_DOCKER_EXEC" = true ]; then
        docker exec ${CONTAINER_NAME} mysql -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SHOW TABLES;" 2>/dev/null || echo "   (表列表获取失败或表尚未创建)"
    else
        mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -e "SHOW TABLES;" 2>/dev/null || echo "   (表列表获取失败或表尚未创建)"
    fi
    echo ""
else
    echo ""
    echo -e "${RED}❌ 數據庫初始化失敗${NC}"
    exit 1
fi

