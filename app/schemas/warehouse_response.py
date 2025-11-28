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
    cabinet_id: Optional[UUID]
    room_id: Optional[int]
    home_id: int
    name: str
    description: Optional[str]
    quantity: int
    min_stock_alert: int
    photo: Optional[str]
    url: Optional[str] = None  # 照片的完整访问 URL（与 photo 相同，用于兼容）
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
    children: Optional[List["CategoryResponse"]] = None  # 子分类列表（用于层级结构）
    
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


# ==================== Log Response Schemas ====================

class LogResponse(BaseModel):
    """Log 响应"""
    id: UUID
    home_id: int
    created_at: datetime
    state: int  # 0=新增（create），1=更新（modify），2=删除（delete），后续可能扩充
    item_type: int  # 0=cabinet, 1=item
    operate_type: Optional[List[int]] = None  # 操作类型数组：0=name, 1=description, 2=move, 3=quantity, 4=photo，后续可能扩充
    user_name: str
    type: int  # 0=一般（normal），1=警告（warning），后续可能扩充
    
    class Config:
        from_attributes = True

