#!/bin/bash

# 獲取腳本所在目錄的絕對路徑
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/../../docker"

# 進入 docker 目錄並啟動 MySQL 服務
cd "$DOCKER_DIR" && docker-compose -f docker-compose.dev.yml up -d warehouse-mysql-dev
