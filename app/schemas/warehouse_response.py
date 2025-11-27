from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


# ==================== Cabinet Response Schemas ====================

class CabinetResponse(BaseModel):
    """Cabinet 响应"""
    id: UUID
    room_id: Optional[int]
    home_id: int
    name: str
    description: Optional[str]
    
    class Config:
        from_attributes = True


# ==================== Item Response Schemas ====================

class ItemResponse(BaseModel):
    """Item 响应"""
    id: UUID
    cabinet_id: UUID
    room_id: int
    home_id: int
    name: str
    description: Optional[str]
    quantity: int
    min_stock_alert: int
    photo: Optional[str]
    categories: Optional[List["CategoryResponse"]] = None
    
    class Config:
        from_attributes = True


# ==================== Category Response Schemas ====================

class CategoryResponse(BaseModel):
    """Category 响应"""
    id: UUID
    home_id: int
    name: str
    parent_id: Optional[UUID]
    level: int
    
    class Config:
        from_attributes = True


# ==================== Item Log Response Schemas ====================

class ItemLogResponse(BaseModel):
    """Item Log 响应"""
    id: UUID
    item_id: UUID
    type: int  # 1=一般信息异动记录，2=告警类型
    log_message: str
    
    class Config:
        from_attributes = True

