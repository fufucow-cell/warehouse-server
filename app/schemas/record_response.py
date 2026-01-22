from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class RecordResponseModel(BaseModel):
    id: UUID
    household_id: str
    item_id: Optional[UUID] = None
    user_name: Optional[str] = None
    created_at: Optional[int] = None  # epoch milliseconds
    operate_type: Optional[int] = None
    entity_type: Optional[int] = None
    item_name: Optional[List[Optional[str]]] = None  # [0] = old, [1] = new
    item_description: Optional[List[Optional[str]]] = None  # [0] = old, [1] = new
    item_photo: Optional[List[Optional[str]]] = None  # [0] = old, [1] = new
    item_min_stock_count: Optional[List[Optional[int]]] = None  # [0] = old, [1] = new
    category_name: Optional[List[Optional[str]]] = None  # [0] = old, [1] = new
    cabinet_name: Optional[List[Optional[str]]] = None  # [0] = old, [1] = new
    cabinet_room_name: Optional[List[Optional[str]]] = None  # [0] = old, [1] = new (原 room_name)
    quantity_count: Optional[List[Optional[int]]] = None  # [0] = old, [1] = new
