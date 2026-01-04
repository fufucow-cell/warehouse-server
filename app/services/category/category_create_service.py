from typing import List, Optional, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table import Category
from app.schemas.category_request import CreateCategoryRequestModel, ReadCategoryRequestModel
from app.schemas.category_response import CategoryResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.services.record_service import create_record
from app.services.category.category_read_service import read_category, get_level_names
from app.table.record import OperateType, EntityType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))
MAX_LEVEL_NUM = 3

# ==================== Create ====================
async def create_category(
    request_model: CreateCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    categories_query = select(Category).where(
        Category.household_id == uuid_to_str(request_model.household_id),
    )
    result = await db.execute(categories_query)
    all_categories = list(result.scalars().all())

    level_name = await get_level_names(
        category_id=request_model.parent_id,
        db=db
    )
    level_name.append(request_model.name)

    if len(level_name) > MAX_LEVEL_NUM:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    _check_duplicate_category_name(
        categories=all_categories,
        name=request_model.name,
        parent_id=request_model.parent_id,
    )
    
    now_utc8 = datetime.now(UTC_PLUS_8)
    new_category = Category(
        household_id=uuid_to_str(request_model.household_id),
        name=request_model.name,
        parent_id=uuid_to_str(request_model.parent_id),
        created_at=now_utc8,
        updated_at=now_utc8,
    )
    db.add(new_category)
    await db.flush()
    
    await _create_record(
        household_id=request_model.household_id,
        user_name=request_model.user_name,
        operate_type=OperateType.CREATE.value,
        category_name_new=";".join(level_name),
        db=db
    )
    
    return await read_category(
        ReadCategoryRequestModel(household_id=request_model.household_id, category_id=new_category.id),
        db
    )

# ==================== Private Method ====================

def _check_duplicate_category_name(
    categories: List[Category],
    name: str,
    parent_id: Optional[UUID],
) -> None:
    parent_id_str = uuid_to_str(parent_id) if parent_id is not None else None
    
    for category in categories:
        if category.name == name:
            if parent_id_str is None and category.parent_id is None:
                raise ValidationError(ServerErrorCode.CATEGORY_NAME_ALREADY_EXISTS_43)
            elif parent_id_str is not None and category.parent_id == parent_id_str:
                raise ValidationError(ServerErrorCode.CATEGORY_NAME_ALREADY_EXISTS_43)

async def _create_record(
    household_id: UUID,
    user_name: str,
    operate_type: int,
    db: AsyncSession,
    category_name_new: Optional[str] = None,
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=household_id,
            user_name=user_name,
            operate_type=operate_type,
            entity_type=EntityType.CATEGORY.value,
            category_name_new=category_name_new,
        ),
        db
    )
