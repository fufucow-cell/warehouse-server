from __future__ import annotations

from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class CategoryResponseModel(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID]
    children: Optional[List[CategoryResponseModel]] = None
