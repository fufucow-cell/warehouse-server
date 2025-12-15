from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
from app.schemas.category_response import CategoryResponseModel

class ItemResponseModel(BaseModel):
    id: UUID
    room_id: Optional[UUID]
    room_name: Optional[str]
    cabinet_id: Optional[UUID]
    cabinet_name: Optional[str]
    category: Optional[CategoryResponseModel] = None
    name: str
    description: Optional[str]
    quantity: int
    min_stock_alert: int
    photo: Optional[str]