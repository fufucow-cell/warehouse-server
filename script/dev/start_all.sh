#!/bin/bash

# 獲取腳本所在目錄的絕對路徑
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 啟動資料庫
"$SCRIPT_DIR/start_db.sh"

# 啟動 API
"$SCRIPT_DIR/start_api.sh"
