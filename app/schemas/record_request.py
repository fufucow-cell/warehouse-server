from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class CreateRecordRequestModel(BaseModel):
    household_id: UUID
    item_id: Optional[UUID] = None
    user_name: str
    operate_type: int
    entity_type: int
    item_name_old: Optional[str] = None
    item_name_new: Optional[str] = None
    item_description_old: Optional[str] = None
    item_description_new: Optional[str] = None
    item_photo_old: Optional[str] = None
    item_photo_new: Optional[str] = None
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

class ReadRecordRequestModel(BaseModel):
    id: Optional[UUID] = None
    item_id: Optional[UUID] = None
    household_id: UUID
    operate_type: Optional[int] = None
    entity_type: Optional[int] = None
    start_date: Optional[int] = None  # epoch milliseconds
    end_date: Optional[int] = None  # epoch milliseconds
