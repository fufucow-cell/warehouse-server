from typing import Optional, List
from uuid import UUID
from app.schemas.item_response import ItemInCabinetInfo
from pydantic import BaseModel

class CabinetResponseModel(BaseModel):
    cabinet_id: Optional[UUID]
    room_id: Optional[UUID]
    name: str
    item_quantity: int
    items: List[ItemInCabinetInfo]


class CabinetInRoomResponseModel(BaseModel):
    room_id: Optional[str]
    cabinet: List[CabinetResponseModel]
