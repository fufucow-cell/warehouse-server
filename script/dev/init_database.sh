#!/bin/bash

# 獲取腳本所在目錄的絕對路徑
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAREHOUSE_SERVER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MIGRATIONS_DIR="$WAREHOUSE_SERVER_DIR/migrations"

# 從 docker-compose 文件讀取資料庫配置
DOCKER_DIR="$WAREHOUSE_SERVER_DIR/docker"
COMPOSE_FILE="$DOCKER_DIR/docker-compose.dev.yml"

DB_HOST="127.0.0.1"
DB_PORT=$(grep -A 15 "warehouse-mysql-dev:" "$COMPOSE_FILE" | grep -E '^\s+-\s+"[0-9]+:[0-9]+"' | head -1 | sed -E 's/.*"([0-9]+):[0-9]+".*/\1/')
DB_USER=$(grep -A 10 "warehouse-mysql-dev:" "$COMPOSE_FILE" | grep "MYSQL_USER:" | head -1 | sed -E 's/.*MYSQL_USER:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
DB_PASSWORD=$(grep -A 10 "warehouse-mysql-dev:" "$COMPOSE_FILE" | grep "MYSQL_PASSWORD:" | head -1 | sed -E 's/.*MYSQL_PASSWORD:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")
DB_NAME=$(grep -A 10 "warehouse-mysql-dev:" "$COMPOSE_FILE" | grep "MYSQL_DATABASE:" | head -1 | sed -E 's/.*MYSQL_DATABASE:[[:space:]]*([^[:space:]]+).*/\1/' | tr -d '"' | tr -d "'")

# 執行 migrations 目錄中的所有 SQL 文件
find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.sql" -type f | sort | while read sql_file; do
    mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME} < "$sql_file"
done
