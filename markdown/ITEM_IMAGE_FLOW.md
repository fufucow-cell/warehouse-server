# Item 图片处理流程文档

本文档详细说明 Item（物品）图片从客户端接收到服务器回传的完整流程。

## 目录

1. [概述](#概述)
2. [接收流程（创建/更新 Item）](#接收流程创建更新-item)
3. [存储机制](#存储机制)
4. [回传流程（查询 Item）](#回传流程查询-item)
5. [图片访问流程](#图片访问流程)
6. [错误处理](#错误处理)
7. [配置说明](#配置说明)
8. [示例](#示例)

---

## 概述

Item 图片处理采用 **base64 编码传输 + 文件存储 + URL 关联** 的方式：

- **传输方式**：客户端通过 JSON 请求体发送 base64 编码的图片
- **存储方式**：服务器将图片保存为文件，URL 存储在数据库
- **关联方式**：通过 Item 表的 `photo` 字段存储图片 URL
- **访问方式**：客户端通过返回的 URL 访问图片

---

## 接收流程（创建/更新 Item）

### 1. 客户端请求

**创建 Item 请求示例：**
```json
POST /api/v1/warehouse/item/
{
  "home_id": 1,
  "name": "笔记本电脑",
  "photo": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
}
```

**更新 Item 请求示例：**
```json
PUT /api/v1/warehouse/item/
{
  "item_id": "123e4567-e89b-12d3-a456-426614174000",
  "photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**支持的 base64 格式：**
- `data:image/jpeg;base64,xxx` 或 `data:image/jpg;base64,xxx` → 保存为 `.jpg`
- `data:image/png;base64,xxx` → 保存为 `.png`
- 直接 base64 字符串（无前缀）→ 默认保存为 `.jpg`

**限制：**
- 仅支持 **jpg** 和 **png** 格式
- 图片大小限制：**2MB**（warehouse_server 配置）
- 请求体大小限制：**500KB**（API Gateway 限制）

### 2. API Gateway 处理

**路径：** `api_gateway/app/middleware/body_size_limit.py`

**流程：**
1. 检查请求方法（GET/HEAD/OPTIONS 跳过）
2. 检查 `Content-Length` header
3. 判断是否为文件上传请求（`/api/v1/warehouse/upload/*`）
   - 文件上传：限制 500KB
   - 普通 API：限制 500KB
4. 如果超过限制，返回错误 `REQUEST_PARAMETERS_INVALID_1`
5. 验证 Token（`AuthenticationMiddleware`）
6. 转发请求到 Warehouse Server

**代码位置：**
```python
# api_gateway/app/middleware/body_size_limit.py
class BodySizeLimitMiddleware:
    async def dispatch(self, request: Request, call_next):
        # 检查 Content-Length
        if body_size > max_size:
            return error_response(...)
```

### 3. Warehouse Server 处理

#### 3.1 创建 Item（`item_create.py`）

**路径：** `warehouse_server/app/routers/warehouse/item/item_create.py`

**流程：**
```python
# 1. 接收请求
request_data: CreateItemRequest

# 2. 处理 base64 图片
if request_data.photo:
    photo_url, error_msg = save_base64_image(request_data.photo)
    if not photo_url:
        return error_response(...)
    request_data.photo = photo_url  # 替换为 URL

# 3. 创建 Item（photo 字段存储 URL）
new_item = Item(
    name=request_data.name,
    photo=request_data.photo  # URL 字符串
)

# 4. 返回响应（包含 photo URL）
return success_response(data=ItemResponse.model_validate(new_item))
```

#### 3.2 更新 Item（`item_update.py`）

**路径：** `warehouse_server/app/routers/warehouse/item/item_update.py`

**流程：**
```python
# 1. 获取旧图片 URL
old_item = await db.get(Item, item_id)
old_photo_url = old_item.photo

# 2. 保存新图片
photo_url, error_msg = save_base64_image(request_data.photo)

# 3. 删除旧图片文件
if old_photo_url:
    delete_uploaded_file(old_photo_url)

# 4. 更新 Item
item.photo = photo_url
```

### 4. Base64 图片处理

**路径：** `warehouse_server/app/utils/util_file.py`

**函数：** `save_base64_image(base64_str: str)`

**处理步骤：**

1. **解析 base64 字符串**
   ```python
   if base64_str.startswith("data:image/"):
       header, base64_data = base64_str.split(",", 1)
       # 提取文件类型：jpeg/jpg → .jpg, png → .png
   ```

2. **验证格式**
   - 仅支持 `.jpg` 和 `.png`
   - 其他格式返回错误

3. **解码 base64**
   ```python
   image_data = base64.b64decode(base64_data)
   ```

4. **验证文件大小**
   - 检查是否为空
   - 检查是否超过 `MAX_UPLOAD_SIZE`（2MB）

5. **生成文件名**
   ```python
   unique_filename = f"{uuid.uuid4()}{file_extension}"
   # 示例：a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
   ```

6. **创建目录结构**
   ```python
   date_dir = datetime.now().strftime("%Y/%m/%d")
   # 示例：2025/11/28
   save_dir = upload_base_dir / date_dir
   ```

7. **保存文件**
   ```python
   file_path = save_dir / unique_filename
   with open(file_path, "wb") as f:
       f.write(image_data)
   ```

8. **返回 URL**
   ```python
   file_url = f"/api/v1/warehouse/{settings.UPLOAD_DIR}/{date_dir}/{unique_filename}"
   # 示例：/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
   return file_url, None
   ```

---

## 存储机制

### 文件系统存储

**物理路径：**
```
warehouse_server/uploads/YYYY/MM/DD/uuid.jpg
```

**示例：**
```
warehouse_server/
  uploads/
    2025/
      11/
        28/
          a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
          b2c3d4e5-f6a7-8901-bcde-f12345678901.png
```

**特点：**
- 按日期分组存储（`YYYY/MM/DD`）
- 文件名使用 UUID 确保唯一性
- 扩展名：`.jpg` 或 `.png`

### 数据库存储

**表结构：** `item` 表

**字段：**
```sql
photo VARCHAR(500)  -- 存储图片 URL
```

**存储内容：**
```
/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
```

**关联关系：**
- 一对一：一个 Item 对应一张图片（`photo` 字段）
- 通过 `item_id` 查询 Item，然后获取 `item.photo` 字段

---

## 回传流程（查询 Item）

### 1. 查询接口

**路径：** `warehouse_server/app/routers/warehouse/item/item_fetch.py`

**支持的查询方式：**
- 按 `item_id` 查询单个 Item
- 按 `cabinet_id` 查询橱柜下的所有 Item
- 按 `home_id` 查询家庭下的所有 Item

### 2. 构建响应数据

**函数：** `_build_item_response_data(item: Item)`

**流程：**
```python
# 1. 从数据库查询 Item
item = await db.get(Item, item_id)

# 2. 转换为响应格式
response_data = ItemResponse.model_validate(item).model_dump(
    mode="json",
    exclude_none=True,
)

# 3. 设置 url 字段（与 photo 相同，用于兼容）
if response_data.get("photo"):
    response_data["url"] = response_data["photo"]

# 4. 返回响应
return success_response(data=response_data)
```

### 3. 响应格式

**单个 Item 响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "笔记本电脑",
    "photo": "/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    "url": "/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    "quantity": 1,
    ...
  },
  "request_id": "..."
}
```

**多个 Item 响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": "...",
      "name": "物品1",
      "photo": "/api/v1/warehouse/uploads/2025/11/28/uuid1.jpg",
      ...
    },
    {
      "id": "...",
      "name": "物品2",
      "photo": "/api/v1/warehouse/uploads/2025/11/28/uuid2.png",
      ...
    }
  ],
  "request_id": "..."
}
```

**字段说明：**
- `photo`：图片 URL（存储在数据库中的值）
- `url`：图片 URL（与 `photo` 相同，用于兼容性）

---

## 图片访问流程

### 1. 客户端请求图片

**完整 URL：**
```
http://localhost:8000/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
```

**相对 URL（从响应中获取）：**
```
/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
```

### 2. API Gateway 代理

**路径：** `api_gateway/app/routers/warehouse.py`

**函数：** `_proxy_static_file(request: Request, path: str)`

**流程：**
```python
# 1. 识别静态文件请求
if path.startswith("uploads/"):
    return await _proxy_static_file(request, path)

# 2. 构建 Warehouse Server URL
full_url = f"{settings.WAREHOUSE_SERVER_URL}/{path}"
# 示例：http://localhost:8003/uploads/2025/11/28/uuid.jpg

# 3. 转发请求到 Warehouse Server
response = await client.request(
    method=request.method,
    url=full_url,
    ...
)

# 4. 返回文件内容
return Response(
    content=response.content,
    status_code=response.status_code,
    media_type=response.headers.get("content-type")
)
```

### 3. Warehouse Server 静态文件服务

**路径：** `warehouse_server/main.py`

**配置：**
```python
# 静态文件服务
upload_dir = Path(__file__).parent / settings.UPLOAD_DIR
app.mount(f"/{settings.UPLOAD_DIR}", StaticFiles(directory=str(upload_dir)), name="uploads")
```

**访问路径映射：**
```
/uploads/2025/11/28/uuid.jpg
  ↓
warehouse_server/uploads/2025/11/28/uuid.jpg
```

### 4. 返回图片内容

**响应：**
- `Content-Type`: `image/jpeg` 或 `image/png`
- `Content-Length`: 文件大小
- `Body`: 图片二进制数据

---

## 错误处理

### 1. 接收阶段错误

| 错误场景 | 错误码 | 说明 |
|---------|--------|------|
| 请求体超过 500KB | `REQUEST_PARAMETERS_INVALID_1` | API Gateway 拦截 |
| Token 无效 | `UNAUTHORIZED_42` | 认证失败 |
| Base64 格式错误 | `REQUEST_PARAMETERS_INVALID_42` | 无法解析 base64 |
| 图片格式不支持 | `REQUEST_PARAMETERS_INVALID_42` | 仅支持 jpg/png |
| 图片文件过大 | `REQUEST_PARAMETERS_INVALID_42` | 超过 2MB 限制 |
| 图片文件为空 | `REQUEST_PARAMETERS_INVALID_42` | base64 解码后为空 |

### 2. 存储阶段错误

| 错误场景 | 处理方式 |
|---------|---------|
| 目录创建失败 | 记录日志，返回错误 |
| 文件写入失败 | 记录日志，返回错误 |
| 数据库保存失败 | 回滚事务，文件可能残留（需清理） |

### 3. 查询阶段错误

| 错误场景 | 错误码 | 说明 |
|---------|--------|------|
| Item 不存在 | `REQUEST_PATH_INVALID_40` | item_id 无效 |
| 未授权 | `UNAUTHORIZED_40` | Token 无效 |

### 4. 访问阶段错误

| 错误场景 | HTTP 状态码 | 说明 |
|---------|------------|------|
| 文件不存在 | `404` | 文件路径无效或文件已删除 |
| 路径格式错误 | `404` | URL 格式不正确 |

---

## 配置说明

### API Gateway 配置

**文件：** `api_gateway/app/core/core_config.py`

```python
# 请求体大小限制
MAX_REQUEST_BODY_SIZE: int = 500 * 1024  # 500KB
MAX_UPLOAD_BODY_SIZE: int = 500 * 1024   # 500KB
```

### Warehouse Server 配置

**文件：** `warehouse_server/app/core/core_config.py`

```python
# 文件上传配置
UPLOAD_DIR: str = "uploads"  # 文件上传目录
MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024  # 最大文件大小：2MB
ALLOWED_IMAGE_EXTENSIONS: list[str] = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
# 注意：base64 图片仅支持 .jpg 和 .png
```

---

## 示例

### 完整流程示例

#### 1. 创建 Item 并上传图片

**请求：**
```bash
curl -X POST "http://localhost:8000/api/v1/warehouse/item/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "home_id": 1,
    "name": "笔记本电脑",
    "photo": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
  }'
```

**响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "笔记本电脑",
    "photo": "/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    "url": "/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    "quantity": 0,
    "min_stock_alert": 0
  },
  "request_id": "..."
}
```

**文件系统：**
```
warehouse_server/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
```

**数据库：**
```sql
SELECT id, name, photo FROM item WHERE id = '123e4567-e89b-12d3-a456-426614174000';

id: 123e4567-e89b-12d3-a456-426614174000
name: 笔记本电脑
photo: /api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
```

#### 2. 查询 Item 并获取图片 URL

**请求：**
```bash
curl -X GET "http://localhost:8000/api/v1/warehouse/item/?item_id=123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer <token>"
```

**响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "笔记本电脑",
    "photo": "/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    "url": "/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    ...
  },
  "request_id": "..."
}
```

#### 3. 访问图片

**请求：**
```bash
curl "http://localhost:8000/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
```

**响应：**
- `Content-Type: image/jpeg`
- `Body`: 图片二进制数据

#### 4. 更新 Item 图片

**请求：**
```bash
curl -X PUT "http://localhost:8000/api/v1/warehouse/item/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "123e4567-e89b-12d3-a456-426614174000",
    "photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
  }'
```

**处理流程：**
1. 获取旧图片 URL：`/api/v1/warehouse/uploads/2025/11/28/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg`
2. 保存新图片：`/api/v1/warehouse/uploads/2025/11/28/b2c3d4e5-f6a7-8901-bcde-f12345678901.png`
3. 删除旧图片文件
4. 更新数据库中的 `photo` 字段

---

## 总结

### 数据流图

```
客户端
  ↓ (1) POST /api/v1/warehouse/item/ { photo: "data:image/jpeg;base64,..." }
API Gateway
  ↓ (2) 验证 Token、检查请求体大小
Warehouse Server
  ↓ (3) 解析 base64、保存文件、存储 URL 到数据库
  ↓ (4) 返回响应 { photo: "/api/v1/warehouse/uploads/..." }
客户端
  ↓ (5) GET /api/v1/warehouse/item/?item_id=...
API Gateway
  ↓ (6) 转发查询请求
Warehouse Server
  ↓ (7) 查询数据库、返回 Item（包含 photo URL）
客户端
  ↓ (8) GET /api/v1/warehouse/uploads/.../uuid.jpg
API Gateway
  ↓ (9) 代理静态文件请求
Warehouse Server
  ↓ (10) 返回图片二进制数据
客户端
```

### 关键点

1. **传输方式**：base64 编码在 JSON 中传输
2. **存储方式**：文件存储在文件系统，URL 存储在数据库
3. **关联方式**：通过 Item 表的 `photo` 字段关联
4. **访问方式**：通过 URL 访问，API Gateway 代理到 Warehouse Server
5. **格式限制**：仅支持 jpg 和 png
6. **大小限制**：请求体 500KB，图片文件 2MB

---

**文档版本：** 1.0  
**最后更新：** 2025-11-28

