from typing import Optional, Union
from uuid import UUID
from pydantic import BaseModel, field_validator

class CreateItemRequestModel(BaseModel):
    household_id: UUID
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
    cabinet_id: Optional[UUID] = None
    category_ids: Optional[list[UUID]] = None

class UpdateItemRequestModel(BaseModel):
    id: UUID
    household_id: UUID
    cabinet_id: Optional[Union[str, UUID]] = None
    category_id: Optional[Union[str, UUID]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    min_stock_alert: Optional[int] = None
    photo: Optional[str] = None
    user_name: str
    
    @field_validator('cabinet_id', mode='before')
    @classmethod
    def validate_cabinet_id(cls, v):
        if v == "" or v is None:
            return None
        return v
    
    @field_validator('category_id', mode='before')
    @classmethod
    def validate_category_id(cls, v):
        if v == "" or v is None:
            return None
        return v

class DeleteItemRequestModel(BaseModel):
    id: UUID
    household_id: UUID
    user_name: str


class CabinetInfo(BaseModel):
    cabinet_id: Optional[UUID] = None
    cabinet_name: Optional[str] = None
    room_id: Optional[UUID] = None


class CabinetUpdateInfo(BaseModel):
    old: CabinetInfo
    new: CabinetInfo


class CategoryInfo(BaseModel):
    category_id: Optional[UUID] = None
    level_name: Optional[str] = None


class CategoryUpdateInfo(BaseModel):
    old: CategoryInfo
    new: CategoryInfo
