# Warehouse Server

倉庫管理系統後端服務，提供物品、分類、櫃子、記錄等核心功能的 API 服務。

## 📋 目錄

- [技術棧](#技術棧)
- [環境要求](#環境要求)
- [快速開始](#快速開始)
- [配置說明](#配置說明)
- [資料庫設置](#資料庫設置)
- [運行方式](#運行方式)
- [API 文檔](#api-文檔)
- [專案結構](#專案結構)
- [開發指南](#開發指南)

## 🛠 技術棧

### 核心框架與版本

| 技術 | 版本 | 說明 |
|------|------|------|
| Python | 3.9+ | 推薦使用 Python 3.9.6 或更高版本 |
| FastAPI | 0.104.1 | 現代、快速的 Web 框架 |
| Uvicorn | 0.24.0 | ASGI 伺服器 |
| SQLAlchemy | 2.0.23 | ORM 框架（非同步支援） |
| Pydantic | 2.5.0 | 資料驗證和設置管理 |
| MySQL | 8.0+ | 資料庫（透過 Docker 運行） |

### 主要依賴

- **aiomysql** (0.2.0) - MySQL 非同步驅動
- **python-jose** (3.3.0) - JWT 令牌處理
- **passlib** (1.7.4) - 密碼雜湊
- **httpx** (0.25.2) - HTTP 客戶端
- **python-multipart** (0.0.6) - 檔案上傳支援

完整依賴列表請查看 [requirements.txt](./requirements.txt)

## 📦 環境要求

### 系統要求

- **作業系統**: macOS, Linux, 或 Windows (WSL2)
- **Python**: 3.9.6 或更高版本
- **Docker**: 20.10+ (用於運行 MySQL)
- **Docker Compose**: 1.29+ (用於開發環境)

### 開發工具（推薦）

- Git
- VS Code 或 PyCharm
- MySQL 客戶端工具（可選，用於資料庫管理）

## 🚀 快速開始

### 1. 克隆專案

```bash
git clone https://github.com/fufucow-cell/warehouse-server.git
cd warehouse-server
```

### 2. 建立虛擬環境

```bash
# 使用 venv
python3 -m venv venv

# 啟動虛擬環境
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 3. 安裝依賴

```bash
pip install -r requirements.txt
```

### 4. 配置環境變數

建立 `.env` 檔案（參考 [配置說明](#配置說明)）：

```bash
cp .env.example .env  # 如果有範例檔案
# 或直接建立 .env 檔案
```

### 5. 啟動資料庫

**方式一：使用腳本（推薦）**

```bash
cd script/dev
bash start_db.sh
```

**方式二：使用 Docker Compose 直接啟動**

```bash
cd docker
docker-compose -f docker-compose.dev.yml up -d warehouse-mysql-dev
```

### 6. 初始化資料庫

```bash
cd script/dev
bash init_database.sh
```

### 7. 啟動服務

**方式一：使用腳本啟動完整服務（推薦）**

```bash
# 啟動資料庫 + API 服務（使用 Docker）
cd script/dev
bash start_all.sh
```

**方式二：本地開發模式（自動重載）**

```bash
# 啟動虛擬環境（如果尚未啟動）
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows

# 啟動服務（自動重載）
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

**方式三：使用 Docker Compose 啟動完整服務**

```bash
cd docker
docker-compose -f docker-compose.dev.yml up
```

### 8. 驗證服務

存取以下 URL 驗證服務是否正常運行：

- API 文檔: http://localhost:8003/docs
- 健康檢查: http://localhost:8003/health

## ⚙️ 配置說明

### 必須修改的配置參數

在使用本服務前，**必須**修改以下配置參數：

#### 1. 資料庫配置

在 `.env` 檔案或環境變數中設置：

```env
# 資料庫連接配置
DB_HOST=localhost          # 資料庫主機位址
DB_PORT=3307               # 資料庫埠（開發環境預設 3307）
DB_USER=cowlin             # ⚠️ 必須修改：資料庫使用者名稱
DB_PASSWORD=abc123         # ⚠️ 必須修改：資料庫密碼（生產環境使用強密碼）
DB_NAME=smartwarehouse_warehouse_dev  # 資料庫名稱
DB_DRIVER=mysql            # 資料庫驅動
```

**⚠️ 安全提示**: 
- 生產環境必須修改 `DB_USER` 和 `DB_PASSWORD`
- 使用強密碼（至少 16 個字元，包含大小寫字母、數字和特殊字元）
- 不要將包含密碼的 `.env` 檔案提交到版本控制系統

#### 2. JWT 金鑰配置

```env
# JWT 配置（與 auth_server 共享）
JWT_SECRET_KEY=your-secret-key-change-this-in-production  # ⚠️ 必須修改：使用隨機產生的金鑰
JWT_ALGORITHM=HS256
```

**⚠️ 安全提示**:
- 生產環境必須修改 `JWT_SECRET_KEY`
- 使用安全的隨機字串（建議至少 32 個字元）
- 可以使用以下命令產生：
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

#### 3. CORS 配置

```env
# CORS 配置（允許的前端網域）
CORS_ORIGINS=http://localhost:3000,http://localhost:8080  # ⚠️ 生產環境必須修改為實際前端網域
# 開發環境可以使用 "*" 允許所有來源
```

**⚠️ 安全提示**:
- 生產環境**不要**使用 `CORS_ORIGINS=*`
- 明確指定允許的前端網域，使用逗號分隔多個網域

#### 4. 服務位址配置

```env
# API 服務配置
API_HOST=0.0.0.0           # 服務監聽位址
API_PORT=8003              # 服務埠

# 圖片 URL 基礎位址（用於產生完整的圖片存取 URL）
BASE_URL=http://localhost:8000  # ⚠️ 必須修改：根據實際部署環境修改
```

**說明**:
- `BASE_URL`: 如果透過 API Gateway 存取，設置為 Gateway 位址
- 如果直接存取，設置為 `http://<伺服器IP>:8003`

#### 5. 其他服務配置

```env
# 內部服務配置（用於跨服務呼叫）
HOUSEHOLD_SERVER_URL=http://localhost:8002  # ⚠️ 根據實際部署環境修改
```

### 完整配置參數列表

所有可配置參數及其預設值：

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `API_HOST` | str | `0.0.0.0` | API 服務監聽位址 |
| `API_PORT` | int | `8003` | API 服務埠 |
| `API_DEBUG` | bool | `False` | 除錯模式開關 |
| `APP_ENV` | str | `dev` | 應用環境（dev/prod） |
| `APP_NAME` | str | `warehouse_server` | 應用名稱 |
| `DB_HOST` | str | `localhost` | 資料庫主機 |
| `DB_PORT` | int | `3307` | 資料庫埠 |
| `DB_USER` | str | `cowlin` | 資料庫使用者名稱 |
| `DB_PASSWORD` | str | `abc123` | 資料庫密碼 |
| `DB_NAME` | str | `smartwarehouse_warehouse_dev` | 資料庫名稱 |
| `DB_DRIVER` | str | `mysql` | 資料庫驅動 |
| `JWT_SECRET_KEY` | str | `your-secret-key...` | JWT 金鑰 |
| `JWT_ALGORITHM` | str | `HS256` | JWT 演算法 |
| `HOUSEHOLD_SERVER_URL` | str | `http://localhost:8002` | 內部服務位址 |
| `CORS_ORIGINS` | str | `*` | CORS 允許來源 |
| `ENABLE_LOG` | bool | `True` | 日誌開關 |
| `UPLOAD_DIR` | str | `uploads` | 檔案上傳目錄 |
| `MAX_UPLOAD_SIZE` | int | `2097152` | 最大上傳大小（2MB） |
| `BASE_URL` | str | `http://localhost:8000` | 圖片 URL 基礎位址 |

### 配置方式

配置可以透過以下方式設置（按優先級從高到低）：

1. **環境變數** - 系統環境變數
2. **`.env` 檔案** - 專案根目錄下的 `.env` 檔案
3. **預設值** - `app/core/core_config.py` 中定義的預設值

## 🗄️ 資料庫設置

### 前置條件

1. 確保 MySQL 容器正在運行
2. 確認資料庫連接資訊

**檢查容器狀態：**
```bash
docker ps | grep warehouse-mysql-dev
```

如果容器未運行，先啟動：
```bash
cd docker
docker-compose -f docker-compose.dev.yml up -d warehouse-mysql-dev
```

等待 10-30 秒讓 MySQL 完全啟動。

### 資料庫連接資訊

| 項目 | 值 |
|------|-----|
| **容器名** | `warehouse-mysql-dev` |
| **資料庫名** | `smartwarehouse_warehouse_dev` |
| **用户名** | `cowlin` |
| **密碼** | `abc123` |
| **主機（容器內）** | `localhost` 或 `warehouse-mysql-dev` |
| **主機（外部）** | `localhost` |
| **端口（容器內）** | `3306` |
| **端口（外部）** | `3307` |

### 初始化資料庫表

#### 方法 1：使用腳本（推薦）

```bash
# 啟動資料庫
cd script/dev
bash start_db.sh

# 初始化資料庫表（自動執行 migrations 目錄下的所有 SQL 文件）
bash init_database.sh

# 停止資料庫（需要時）
bash stop_db.sh
```

#### 方法 2：使用 Docker exec 執行 SQL 文件

1. **進入專案根目錄**
   ```bash
   cd /Users/cow/Desktop/work/warehouse/backend/warehouse_server
   ```

2. **執行 SQL 文件**
   ```bash
   docker exec -i warehouse-mysql-dev mysql -u cowlin -pabc123 smartwarehouse_warehouse_dev < migrations/001_create_default_tables.sql
   ```

3. **驗證表是否創建成功**
   ```bash
   # 查看所有表
   docker exec -i warehouse-mysql-dev mysql -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "SHOW TABLES;"
   
   # 查看表結構
   docker exec -i warehouse-mysql-dev mysql -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "DESCRIBE category;"
   ```

#### 方法 3：使用本地 MySQL 客戶端

**前置條件：** 需要本地安裝 MySQL 客戶端

**macOS:**
```bash
brew install mysql-client
```

**執行 SQL 文件：**
```bash
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev < migrations/001_create_default_tables.sql
```

**驗證表是否創建成功：**
```bash
# 查看所有表
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "SHOW TABLES;"

# 查看表結構
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "DESCRIBE category;"
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "DESCRIBE cabinet;"
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "DESCRIBE item;"
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "DESCRIBE record;"

# 進入 MySQL 命令行查看（交互式）
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev
# 然後在 MySQL 命令行中執行：
# SHOW TABLES;
# DESCRIBE category;
# SELECT * FROM category LIMIT 10;
# exit;
```

### 資料庫表結構

主要資料表：

- `category` - 分類表（支援多級分類，支援自引用）
- `cabinet` - 櫃子表
- `item` - 物品表（關聯分類和櫃子）
- `record` - 操作記錄表（審計日誌）

詳細表結構請查看 [migrations/001_create_default_tables.sql](./migrations/001_create_default_tables.sql)

**驗證表結構：**

```bash
# 查看所有表和行數
docker exec -i warehouse-mysql-dev mysql -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "
SELECT 
    TABLE_NAME as '表名',
    TABLE_ROWS as '行數',
    CREATE_TIME as '創建時間'
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'smartwarehouse_warehouse_dev'
ORDER BY TABLE_NAME;
"

# 查看所有索引
docker exec -i warehouse-mysql-dev mysql -u cowlin -pabc123 smartwarehouse_warehouse_dev -e "
SELECT 
    TABLE_NAME,
    INDEX_NAME,
    COLUMN_NAME,
    SEQ_IN_INDEX
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'smartwarehouse_warehouse_dev'
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
"
```

### 常見問題

#### 1. 錯誤：`ERROR 2002 (HY000): Can't connect to MySQL server` 或 `Can't connect to local MySQL server through socket`

**原因：** 
- MySQL 容器未運行或未完全啟動
- 使用 `localhost` 導致嘗試使用 Unix socket 而非 TCP 連接

**解決：**
```bash
# 檢查容器狀態
docker ps | grep warehouse-mysql-dev

# 如果未運行，啟動容器
cd docker
docker-compose -f docker-compose.dev.yml up -d warehouse-mysql-dev

# 等待 10-30 秒讓 MySQL 完全啟動

# 如果使用本地 MySQL 客戶端連接，使用 127.0.0.1 而不是 localhost
mysql -h 127.0.0.1 -P 3307 -u cowlin -pabc123 smartwarehouse_warehouse_dev
```

#### 2. 錯誤：`ERROR 1049 (42000): Unknown database 'smartwarehouse_warehouse_dev'`

**原因：** 資料庫不存在

**解決：**
```bash
# MySQL 容器啟動時會自動創建資料庫，但如果不存在，可以手動創建
docker exec -i warehouse-mysql-dev mysql -u cowlin -pabc123 -e "CREATE DATABASE IF NOT EXISTS smartwarehouse_warehouse_dev;"
```

#### 3. 錯誤：`ERROR 1061 (42000): Duplicate key name 'ix_category_parent_id'`

**原因：** 索引已存在（重複執行 SQL 文件）

**解決：**
- 如果是首次執行遇到此錯誤，說明表結構可能已經部分創建
- 可以刪除表後重新執行，或手動檢查哪些索引已存在

**刪除所有表（謹慎使用）：**
```sql
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS record;
DROP TABLE IF EXISTS item;
DROP TABLE IF EXISTS cabinet;
DROP TABLE IF EXISTS category;
SET FOREIGN_KEY_CHECKS = 1;
```

#### 4. 錯誤：`ERROR 1045 (28000): Access denied`

**原因：** 用戶名或密碼錯誤

**解決：** 檢查 `docker/docker-compose.dev.yml` 中的配置是否正確

## 🏃 運行方式

### 使用腳本（推薦）

**啟動完整服務（資料庫 + API）**

```bash
cd script/dev
bash start_all.sh
```

**停止完整服務**

```bash
cd script/dev
bash stop_all.sh
```

### 開發模式（本地運行）

```bash
# 啟動虛擬環境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows

# 啟動服務（自動重載）
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

### 使用 Docker Compose

**啟動服務**

```bash
cd docker
docker-compose -f docker-compose.dev.yml up
```

**停止服務**

```bash
cd docker
docker-compose -f docker-compose.dev.yml stop
# 或停止所有服務
docker-compose -f docker-compose.dev.yml down
```

### 生產模式

```bash
# 不使用 --reload 參數
uvicorn main:app --host 0.0.0.0 --port 8003 --workers 4
```

## 📚 API 文檔

啟動服務後，可以透過以下位址存取 API 文檔：

- **Swagger UI**: http://localhost:8003/docs
- **ReDoc**: http://localhost:8003/redoc

### 主要 API 端點

- `GET /health` - 健康檢查
- `GET {API_PREFIX}/...` - 倉庫相關 API

詳細 API 文檔請參考 Swagger UI。

## 📁 專案結構

```
warehouse_server/
├── app/                      # 應用主目錄
│   ├── core/                 # 核心配置
│   │   ├── core_config.py   # 配置管理
│   │   ├── core_database.py  # 資料庫配置
│   │   └── core_security.py  # 安全配置
│   ├── db/                   # 資料庫相關
│   │   ├── base.py          # 資料庫基類
│   │   └── session.py        # 資料庫會話
│   ├── routers/              # 路由定義
│   │   ├── cabinet/         # 櫃子相關路由
│   │   ├── category/        # 分類相關路由
│   │   ├── item/            # 物品相關路由
│   │   ├── record/          # 記錄相關路由
│   │   └── health.py        # 健康檢查
│   ├── schemas/              # 資料模型
│   │   ├── *_request.py     # 請求模型
│   │   └── *_response.py    # 響應模型
│   ├── services/             # 業務邏輯
│   │   ├── cabinet_service.py
│   │   ├── category_service.py
│   │   ├── item_service.py
│   │   └── record_service.py
│   ├── table/                # 資料庫表模型
│   │   ├── cabinet.py
│   │   ├── category.py
│   │   ├── item.py
│   │   └── record.py
│   └── utils/                # 工具函數
│       ├── util_error_handle.py
│       ├── util_error_map.py
│       ├── util_file.py
│       ├── util_log.py
│       ├── util_request.py
│       └── util_response.py
├── docker/                   # Docker 配置
│   ├── docker-compose.dev.yml
│   ├── Dockerfile-api.dev
│   └── Dockerfile-mysql.dev
├── migrations/               # 資料庫遷移腳本
│   └── 001_create_default_tables.sql
├── script/                   # 腳本檔案
│   └── dev/                 # 開發環境腳本
├── resource/                 # 資源檔案
│   └── feature_code_map.json
├── main.py                   # 應用入口
├── requirements.txt          # Python 依賴
└── README.md                 # 本檔案
```

## 💻 開發指南

### 程式碼規範

- 遵循 PEP 8 Python 程式碼規範
- 使用類型提示（Type Hints）
- 非同步函數使用 `async/await`
- 使用 Pydantic 進行資料驗證

### 新增功能

1. **定義資料模型** (`app/table/`)
2. **建立 Schema** (`app/schemas/`)
3. **實作業務邏輯** (`app/services/`)
4. **定義路由** (`app/routers/`)
5. **編寫資料庫遷移** (`migrations/`)