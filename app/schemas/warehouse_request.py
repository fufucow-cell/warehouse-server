from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


# ==================== Cabinet Request Schemas ====================

class CreateCabinetRequest(BaseModel):
    """创建 Cabinet 请求"""
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id）")
    room_id: Optional[int] = Field(None, description="Room ID（关联到 household_server.room.id，可选）")
    name: str = Field(..., min_length=1, max_length=255, description="橱柜名称")
    description: Optional[str] = Field(None, max_length=500, description="橱柜描述")


class UpdateCabinetRequest(BaseModel):
    """更新 Cabinet 请求"""
    cabinet_id: UUID = Field(..., description="Cabinet ID（UUID）")
    old_room_id: Optional[int] = Field(None, description="旧 Room ID（关联到 household_server.room.id，用于验证）")
    new_room_id: Optional[int] = Field(None, description="新 Room ID（关联到 household_server.room.id，用于更新）")
    home_id: Optional[int] = Field(None, description="Home ID（关联到 household_server.home.id）")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="橱柜名称")
    description: Optional[str] = Field(None, max_length=500, description="橱柜描述")


class DeleteCabinetRequest(BaseModel):
    """删除 Cabinet 请求"""
    cabinet_id: UUID = Field(..., description="Cabinet ID（UUID）")


# ==================== Item Request Schemas ====================

class CreateItemRequest(BaseModel):
    """创建 Item 请求"""
    cabinet_id: UUID = Field(..., description="Cabinet ID（UUID）")
    room_id: int = Field(..., description="Room ID（关联到 household_server.room.id）")
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id）")
    name: str = Field(..., min_length=1, max_length=255, description="物品名称")
    description: Optional[str] = Field(None, description="物品描述")
    quantity: int = Field(default=0, ge=0, description="物品数量")
    min_stock_alert: int = Field(default=0, ge=0, description="最低库存警报阈值")
    photo: Optional[str] = Field(None, max_length=500, description="照片 URL")
    category_ids: Optional[list[UUID]] = Field(None, description="分类 ID 列表（可选）")


class UpdateItemRequest(BaseModel):
    """更新 Item 请求"""
    item_id: UUID = Field(..., description="Item ID（UUID）")
    room_id: Optional[int] = Field(None, description="Room ID（关联到 household_server.room.id）")
    home_id: Optional[int] = Field(None, description="Home ID（关联到 household_server.home.id）")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="物品名称")
    description: Optional[str] = Field(None, description="物品描述")
    quantity: Optional[int] = Field(None, ge=0, description="物品数量")
    min_stock_alert: Optional[int] = Field(None, ge=0, description="最低库存警报阈值")
    photo: Optional[str] = Field(None, max_length=500, description="照片 URL")
    category_ids: Optional[list[UUID]] = Field(None, description="分类 ID 列表（可选）")


class DeleteItemRequest(BaseModel):
    """删除 Item 请求"""
    item_id: UUID = Field(..., description="Item ID（UUID）")


# ==================== Category Request Schemas ====================

class CreateCategoryRequest(BaseModel):
    """创建 Category 请求"""
    home_id: int = Field(..., description="Home ID（关联到 household_server.home.id）")
    name: str = Field(..., min_length=1, max_length=255, description="分类名称")
    parent_id: Optional[UUID] = Field(None, description="父分类 ID（用于层级关系，第一层为 NULL）")
    level: int = Field(..., ge=1, le=3, description="分类层级：1=第一层，2=第二层，3=第三层")


class UpdateCategoryRequest(BaseModel):
    """更新 Category 请求"""
    category_id: UUID = Field(..., description="Category ID（UUID）")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="分类名称")
    parent_id: Optional[UUID] = Field(None, description="父分类 ID（用于层级关系）")
    level: Optional[int] = Field(None, ge=1, le=3, description="分类层级：1=第一层，2=第二层，3=第三层")


class DeleteCategoryRequest(BaseModel):
    """删除 Category 请求"""
    category_id: UUID = Field(..., description="Category ID（UUID）")

