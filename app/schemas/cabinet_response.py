from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class CabinetResponseModel(BaseModel):
    cabinet_id: UUID
    name: str
    item_count: int

class CabinetResponseListModel(BaseModel):
    room_id: Optional[str]
    cabinet: List[CabinetResponseModel]
