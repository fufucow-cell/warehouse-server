from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class CategoryResponseModel(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID]
    level: int
    children: Optional[List["CategoryResponseModel"]] = None
    
    class Config:
        from_attributes = True
