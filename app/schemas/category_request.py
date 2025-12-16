from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class CreateCategoryRequestModel(BaseModel):
    household_id: UUID
    name: str
    parent_id: Optional[UUID] = None
    user_name: str

class ReadCategoryRequestModel(BaseModel):
    household_id: UUID
    category_id: Optional[UUID] = None

class UpdateCategoryRequestModel(BaseModel):
    household_id: UUID
    category_id: UUID
    name: Optional[str] = None
    parent_id: Optional[str] = None
    user_name: str

class DeleteCategoryRequestModel(BaseModel):
    household_id: UUID
    category_id: UUID
    user_name: str
