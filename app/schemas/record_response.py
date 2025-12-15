from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class RecordResponseModel(BaseModel):
    id: UUID
    household_id: UUID
    user_name: str
    operate_type: int
    entity_type: int
    record_type: int
    item_name_old: Optional[str] = None
    item_name_new: Optional[str] = None
    category_name_old: Optional[str] = None
    category_name_new: Optional[str] = None
    room_name_old: Optional[str] = None
    room_name_new: Optional[str] = None
    cabinet_name_old: Optional[str] = None
    cabinet_name_new: Optional[str] = None
    quantity_count_old: Optional[int] = None
    quantity_count_new: Optional[int] = None
    min_stock_count_old: Optional[int] = None
    min_stock_count_new: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
