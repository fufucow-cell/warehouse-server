from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class CreateCabinetRequestModel(BaseModel):
    household_id: UUID
    room_id: Optional[UUID] = None
    name: str
    user_name: str

class ReadCabinetByRoomRequestModel(BaseModel):
    household_id: UUID
    room_id: Optional[UUID] = None

class ReadCabinetByIdRequestModel(BaseModel):
    household_id: UUID
    cabinet_id: Optional[UUID] = None

class ReadCabinetRequestModel(BaseModel):
    household_id: UUID
    cabinet_ids: Optional[List[UUID]] = None

class UpdateCabinetRequestModel(BaseModel):
    household_id: UUID
    cabinet_id: Optional[UUID] = None
    room_id: Optional[UUID] = None
    name: Optional[str] = None
    user_name: str

class DeleteCabinetRequestModel(BaseModel):
    household_id: UUID
    cabinet_id: UUID
    user_name: str