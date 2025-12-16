from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class CreateCabinetRequestModel(BaseModel):
    household_id: UUID
    room_id: Optional[UUID] = None
    name: Optional[str] = None
    user_name: str

class ReadCabinetRequestModel(BaseModel):
    household_id: UUID
    room_id: Optional[UUID] = None
    cabinet_ids: Optional[List[UUID]] = None

class UpdateCabinetRequestModel(BaseModel):
    household_id: UUID
    room_id: Optional[UUID] = None
    room_name: Optional[str] = None
    cabinet_id: Optional[UUID] = None
    name: Optional[str] = None
    user_name: str

class DeleteCabinetRequestModel(BaseModel):
    id: UUID
    household_id: UUID
    user_name: str
