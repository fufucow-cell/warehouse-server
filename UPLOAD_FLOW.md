# 文件上传数据流说明

## 概述
物品照片上传功能实现了从客户端到服务器本地存储的完整数据流。

## 数据流路径

### 1. 文件上传
```
客户端 → API Gateway → Warehouse Server → 本地存储
```

**请求路径：**
- `POST /api/v1/warehouse/upload/image`
- 通过 API Gateway 代理到 Warehouse Server

**请求格式：**
- `Content-Type: multipart/form-data`
- 文件字段名：`file`
- 支持的文件类型：`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- 最大文件大小：10MB

**认证：**
- 需要在 Header 中携带 `Authorization: Bearer <token>`
- API Gateway 验证 token 后，会注入 `X-User-ID` header

### 2. 文件存储
**存储位置：**
- 本地目录：`warehouse_server/uploads/`
- 目录结构：`uploads/YYYY/MM/DD/uuid.ext`
- 文件名：使用 UUID 确保唯一性

**示例：**
```
warehouse_server/
  uploads/
    2025/
      11/
        27/
          a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
```

### 3. 返回 URL
**响应格式：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "url": "/api/v1/warehouse/uploads/2025/11/27/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
  },
  "request_id": "..."
}
```

### 4. 文件访问
**访问路径：**
- `GET /api/v1/warehouse/uploads/YYYY/MM/DD/uuid.ext`
- 通过 API Gateway 代理到 Warehouse Server 的静态文件服务

**数据流：**
```
客户端 → API Gateway → Warehouse Server 静态文件服务 → 返回文件内容
```

## 配置说明

### Warehouse Server 配置
**文件：** `warehouse_server/app/core/core_config.py`

```python
UPLOAD_DIR: str = "uploads"  # 文件上传目录
MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 最大文件大小：10MB
ALLOWED_IMAGE_EXTENSIONS: list[str] = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
```

### 静态文件服务
**文件：** `warehouse_server/main.py`

```python
app.mount(f"/{settings.UPLOAD_DIR}", StaticFiles(directory=str(upload_dir)), name="uploads")
```

## 使用示例

### 1. 上传文件
```bash
curl -X POST "http://localhost:8000/api/v1/warehouse/upload/image" \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/image.jpg"
```

### 2. 在创建/更新 Item 时使用返回的 URL
```json
{
  "home_id": 1,
  "name": "物品名称",
  "photo": "/api/v1/warehouse/uploads/2025/11/27/uuid.jpg"
}
```

### 3. 访问上传的文件
```bash
curl "http://localhost:8000/api/v1/warehouse/uploads/2025/11/27/uuid.jpg"
```

## 错误处理

### 错误代码
- `422` (REQUEST_PARAMETERS_INVALID_42): 文件类型不支持、文件过大或文件为空
- `424` (UNAUTHORIZED_42): 未认证或认证失败
- `420` (INTERNAL_SERVER_ERROR_42): 服务器内部错误

### 错误响应格式
```json
{
  "code": 110,
  "message": "Request parameters invalid",
  "request_id": "..."
}
```

## 注意事项

1. **文件存储位置**：文件存储在 `warehouse_server/uploads/` 目录下，需要确保该目录有写入权限
2. **文件唯一性**：使用 UUID 作为文件名，确保不会重复
3. **目录结构**：按日期分组存储，便于管理和清理
4. **静态文件访问**：通过 API Gateway 访问，确保统一的访问入口
5. **文件大小限制**：当前限制为 10MB，可根据需要调整配置
6. **文件类型限制**：仅支持图片格式，可根据需要扩展

