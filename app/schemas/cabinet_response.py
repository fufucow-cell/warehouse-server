from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class CabinetResponseModel(BaseModel):
    room_id: Optional[UUID]
    cabinet_id: UUID
    name: str
    item_count: int
