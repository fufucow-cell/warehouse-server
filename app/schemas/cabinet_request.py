from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class CreateCabinetRequestModel(BaseModel):
    household_id: str
    room_id: Optional[str] = None
    room_name: Optional[str] = None
    name: str
    user_name: str

class ReadCabinetRequestModel(BaseModel):
    household_id: str
    room_id: Optional[str] = None
    cabinet_id: Optional[UUID] = None

class UpdateCabinetInfo(BaseModel):
    cabinet_id: UUID
    new_room_id: Optional[str] = None
    new_cabinet_name: Optional[str] = None
    new_room_name: Optional[str] = None
    old_room_name: Optional[str] = None

class UpdateCabinetRequestModel(BaseModel):
    household_id: str
    user_name: str
    cabinets: List[UpdateCabinetInfo]

class DeleteCabinetInfo(BaseModel):
    cabinet_id: UUID
    old_room_name: Optional[str] = None

class DeleteCabinetRequestModel(BaseModel):
    household_id: str
    cabinets: Optional[List[DeleteCabinetInfo]]
    user_name: str