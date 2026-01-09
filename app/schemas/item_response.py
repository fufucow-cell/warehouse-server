from __future__ import annotations

from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
from app.schemas.category_response import CategoryResponseModel

class ItemResponseModel(BaseModel):
    id: UUID
    cabinet_id: Optional[UUID]
    cabinet_name: Optional[str]
    cabinet_room_id: Optional[UUID] = None
    category: Optional[CategoryResponseModel] = None
    name: str
    description: Optional[str]
    quantity: int
    min_stock_alert: int
    photo: Optional[str]

class ItemCategoryResponseModel(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID]
    child: Optional[ItemCategoryResponseModel] = None

class ItemInCabinetInfo(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    quantity: int
    min_stock_alert: int
    photo: Optional[str]
    category: Optional[ItemCategoryResponseModel] = None


class ItemOpenAIRecognitionResult(BaseModel):
    name: str  # 物品名稱
    description: str  # 物品描述
    category_id: Optional[UUID] = None # 分類 ID
    category: str  # 分類
    confidence: int  # 信心度（0-100）