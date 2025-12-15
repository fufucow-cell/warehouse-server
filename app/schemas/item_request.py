from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class CreateItemRequestModel(BaseModel):
    household_id: UUID
    room_id: Optional[UUID] = None
    cabinet_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    quantity: int
    min_stock_alert: int
    photo: Optional[str] = None
    user_name: str

class ReadItemRequestModel(BaseModel):
    household_id: UUID
    room_id: Optional[UUID] = None
    cabinet_id: Optional[UUID] = None
    category_ids: Optional[list[UUID]] = None

class UpdateItemRequestModel(BaseModel):
    id: UUID
    household_id: UUID
    room_id: Optional[UUID] = None
    cabinet_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    quantity: int
    min_stock_alert: int
    photo: Optional[str] = None
    user_name: str

class DeleteItemRequestModel(BaseModel):
    id: UUID
    household_id: UUID
    user_name: str
