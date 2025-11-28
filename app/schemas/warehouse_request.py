from typing import Optional, Union, List
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# ==================== Cabinet Request Schemas ====================

class CreateCabinetRequest(BaseModel):
    """创建 Cabinet 请求"""
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id）")
    room_id: Optional[int] = Field(None, description="Room ID（关联到 household_server.room.id，可选）")
    name: str = Field(..., min_length=1, max_length=255, description="橱柜名称")
    description: Optional[str] = Field(None, max_length=500, description="橱柜描述")
    user_name: str = Field(..., min_length=1, max_length=255, description="用户名")


class UpdateCabinetRequest(BaseModel):
    """更新 Cabinet 请求"""
    cabinet_id: UUID = Field(..., description="Cabinet ID（UUID）")
    new_room_id: Optional[int] = Field(None, description="新 Room ID（关联到 household_server.room.id，用于更新）")
    home_id: Optional[int] = Field(None, description="Home ID（关联到 household_server.home.id）")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="橱柜名称")
    description: Optional[str] = Field(None, max_length=500, description="橱柜描述")
    user_name: str = Field(..., min_length=1, max_length=255, description="用户名")


class DeleteCabinetRequest(BaseModel):
    """删除 Cabinet 请求"""
    cabinet_id: UUID = Field(..., description="Cabinet ID（UUID）")
    user_name: str = Field(..., min_length=1, max_length=255, description="用户名")


# ==================== Item Request Schemas ====================

class CreateItemRequest(BaseModel):
    """创建 Item 请求"""
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id）")
    name: str = Field(..., min_length=1, max_length=255, description="物品名称")
    cabinet_id: Optional[UUID] = Field(None, description="Cabinet ID（UUID，可选）")
    room_id: Optional[int] = Field(None, description="Room ID（关联到 household_server.room.id，可选）")
    description: Optional[str] = Field(None, description="物品描述")
    quantity: int = Field(default=0, ge=0, description="物品数量")
    min_stock_alert: int = Field(default=0, ge=0, description="最低库存警报阈值")
    photo: Optional[str] = Field(None, description="照片 base64 字符串（格式：data:image/jpeg;base64,xxx 或直接 base64 字符串）")
    category_ids: Optional[list[UUID]] = Field(None, description="分类 ID 列表（可选）")
    user_name: str = Field(..., min_length=1, max_length=255, description="用户名")


class UpdateItemRequest(BaseModel):
    """更新 Item 请求"""
    item_id: UUID = Field(..., description="Item ID（UUID）")
    new_cabinet_id: Optional[UUID] = Field(None, description="新 Cabinet ID（UUID，用于更新）")
    new_room_id: Optional[int] = Field(None, description="新 Room ID（关联到 household_server.room.id，用于更新）")
    home_id: Optional[int] = Field(None, description="Home ID（关联到 household_server.home.id）")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="物品名称")
    description: Optional[str] = Field(None, description="物品描述")
    quantity: Optional[int] = Field(None, ge=0, description="物品数量")
    min_stock_alert: Optional[int] = Field(None, ge=0, description="最低库存警报阈值")
    photo: Optional[str] = Field(None, description="照片 base64 字符串（格式：data:image/jpeg;base64,xxx 或直接 base64 字符串）")
    new_category_ids: Optional[list[UUID]] = Field(None, description="新分类 ID 列表（可选）")
    user_name: str = Field(..., min_length=1, max_length=255, description="用户名")


class DeleteItemRequest(BaseModel):
    """删除 Item 请求"""
    item_id: UUID = Field(..., description="Item ID（UUID）")
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id，用于验证物品是否属于该家庭）")
    user_name: str = Field(..., min_length=1, max_length=255, description="用户名")


# ==================== Category Request Schemas ====================

class CreateCategoryRequest(BaseModel):
    """创建 Category 请求"""
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id）")
    name: str = Field(..., min_length=1, max_length=255, description="分类名称")
    parent_id: Optional[UUID] = Field(None, description="父分类 ID（用于层级关系，第一层为 NULL）")
    level: int = Field(..., ge=1, le=3, description="分类层级：1=第一层，2=第二层，3=第三层")
    
    @field_validator('parent_id', mode='before')
    @classmethod
    def validate_parent_id(cls, v):
        """将空字符串转换为 None"""
        if v == "" or v is None:
            return None
        return v


class UpdateCategoryRequest(BaseModel):
    """更新 Category 请求"""
    category_id: UUID = Field(..., description="Category ID（UUID）")
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id，用于验证分类是否属于该家庭）")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="分类名称")
    parent_id: Optional[UUID] = Field(None, description="父分类 ID（用于层级关系）")
    level: Optional[int] = Field(None, ge=1, le=3, description="分类层级：1=第一层，2=第二层，3=第三层")
    
    @field_validator('parent_id', mode='before')
    @classmethod
    def validate_parent_id(cls, v):
        """将空字符串转换为 None"""
        if v == "" or v is None:
            return None
        return v


class DeleteCategoryRequest(BaseModel):
    """删除 Category 请求"""
    category_id: UUID = Field(..., description="Category ID（UUID）")
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id，用于验证分类是否属于该家庭）")


# ==================== Log Request Schemas ====================

class CreateLogRequest(BaseModel):
    """创建 Log 请求"""
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id）")
    state: int = Field(..., description="操作状态：0=新增（create），1=更新（modify），2=删除（delete），后续可能扩充")
    item_type: int = Field(..., description="物品类型：0=cabinet（橱柜），1=item（物品）")
    operate_type: Optional[List[int]] = Field(None, description="操作类型数组：0=name（名称），1=description（描述），2=move（移动），3=quantity（数量），4=photo（照片）。仅在 state=1（modify）时使用，可包含多个操作类型，后续可能扩充")
    user_name: str = Field(..., min_length=1, max_length=255, description="用户名")
    type: int = Field(default=0, description="日志类型：0=一般（normal），1=警告（warning），后续可能扩充")


class FetchLogRequest(BaseModel):
    """获取 Log 请求（用于查询参数）"""
    home_id: Optional[int] = Field(None, description="Home ID（关联到 household_server.home.id）")
    state: Optional[int] = Field(None, description="操作状态：0=新增（create），1=更新（modify），2=删除（delete），后续可能扩充")
    item_type: Optional[int] = Field(None, description="物品类型：0=cabinet（橱柜），1=item（物品）")
    operate_type: Optional[List[int]] = Field(None, description="操作类型数组：0=name（名称），1=description（描述），2=move（移动），3=quantity（数量），4=photo（照片）。用于筛选包含任一操作类型的日志，后续可能扩充")
    type: Optional[int] = Field(None, description="日志类型：0=一般（normal），1=警告（warning），后续可能扩充")


class DeleteLogRequest(BaseModel):
    """删除 Log 请求"""
    log_id: Optional[UUID] = Field(None, description="日志 ID（UUID，可选。如果提供，只删除该日志）")
    home_id: Optional[int] = Field(None, description="Home ID（关联到 household_server.home.id，可选。如果提供，只删除该家庭的日志）")
    retain_time: Optional[int] = Field(None, description="保留时间（Epoch 时间戳，毫秒级整数）。删除 created_at 小于此时间的所有日志。如果未提供，需要 home_id 或 log_id 来指定删除范围")

