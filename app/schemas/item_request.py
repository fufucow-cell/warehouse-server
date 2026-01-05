from typing import List, Optional, Union
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
    room_id: Optional[UUID] = None

class UpdateItemNormalRequestModel(BaseModel):
    item_id: UUID
    household_id: UUID
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
    household_id: UUID
    cabinets: List[UpdateItemQuantityCabinet]
    user_name: str

class UpdateItemPositionCabinet(BaseModel):
    old_cabinet_id: Optional[UUID] = None
    new_cabinet_id: Optional[UUID] = None
    quantity: int

class UpdateItemPositionRequestModel(BaseModel):
    item_id: UUID
    household_id: UUID
    cabinets: List[UpdateItemPositionCabinet]
    user_name: str

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
