from typing import Optional, List
from uuid import UUID
from app.schemas.item_response import ItemInCabinetInfo
from pydantic import BaseModel

class CabinetResponseModel(BaseModel):
    cabinet_id: Optional[UUID]
    room_id: Optional[UUID]
    name: str
    quantity: Optional[int] = None
    items: Optional[List[ItemInCabinetInfo]] = None

class CabinetInRoomResponseModel(BaseModel):
    id: Optional[UUID] = None
    name: str
    quantity: int
    items: List[ItemInCabinetInfo]

class RoomsResponseModel(BaseModel):
    room_id: Optional[str]
    quantity: int
    cabinets: List[CabinetInRoomResponseModel]
