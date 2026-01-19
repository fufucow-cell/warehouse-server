#!/bin/bash

# 獲取腳本所在目錄的絕對路徑
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/../../docker"

# 停止 API 和資料庫
cd "$DOCKER_DIR" && docker-compose -f docker-compose.dev.yml stop warehouse-api-dev warehouse-mysql-dev
