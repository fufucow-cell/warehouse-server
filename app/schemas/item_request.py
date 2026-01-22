from typing import List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, field_validator

class CreateItemRequestModel(BaseModel):
    household_id: str
    cabinet_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    quantity: int
    min_stock_alert: int
    photo: Optional[str] = None
    user_name: str

class ReadItemRequestModel(BaseModel):
    household_id: str
    room_id: Optional[str] = None

class UpdateItemNormalRequestModel(BaseModel):
    item_id: UUID
    household_id: str
    category_id: Optional[Union[str, UUID]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    min_stock_alert: Optional[int] = None
    photo: Optional[str] = None
    user_name: str

class UpdateItemQuantityCabinet(BaseModel):
    cabinet_id: Optional[UUID] = None
    quantity: int

class UpdateItemQuantityRequestModel(BaseModel):
    item_id: UUID
    household_id: str
    cabinets: List[UpdateItemQuantityCabinet]
    user_name: str

class UpdateItemPositionCabinet(BaseModel):
    old_cabinet_id: Optional[UUID] = None
    new_cabinet_id: Optional[UUID] = None
    quantity: Optional[int] = None
    is_delete: bool = False
    
    @field_validator('old_cabinet_id', 'new_cabinet_id', mode='before')
    @classmethod
    def convert_empty_string_to_none(cls, v):
        if v == "":
            return None
        return v

class UpdateItemPositionRequestModel(BaseModel):
    item_id: UUID
    household_id: str
    cabinets: List[UpdateItemPositionCabinet]
    user_name: str

class DeleteItemRequestModel(BaseModel):
    id: UUID
    household_id: str
    user_name: str


class CabinetInfo(BaseModel):
    cabinet_id: Optional[UUID] = None
    cabinet_name: Optional[str] = None
    room_id: Optional[str] = None


class CabinetUpdateInfo(BaseModel):
    old: CabinetInfo
    new: CabinetInfo


class CategoryInfo(BaseModel):
    category_id: Optional[UUID] = None
    level_name: Optional[str] = None


class CategoryUpdateInfo(BaseModel):
    old: CategoryInfo
    new: CategoryInfo


class CreateItemSmartRequestModel(BaseModel):
    household_id: str
    image: str  # base64 encoded image
    language: str
    user_name: str
