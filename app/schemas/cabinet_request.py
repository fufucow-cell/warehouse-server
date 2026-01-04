from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, model_validator

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
    cabinet_id: Optional[UUID] = None
    id: Optional[UUID] = None  # 支持 id 作为 cabinet_id 的别名
    user_name: str
    
    @model_validator(mode='after')
    def validate_cabinet_id(self):
        """如果提供了 id，将其赋值给 cabinet_id；优先使用 cabinet_id"""
        if self.cabinet_id is None:
            if self.id is not None:
                self.cabinet_id = self.id
            else:
                raise ValueError("cabinet_id or id is required")
        # 确保 cabinet_id 不为 None
        if self.cabinet_id is None:
            raise ValueError("cabinet_id or id is required")
        return self