from typing import List, Optional, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from app.table import Category
from app.schemas.category_request import DeleteCategoryRequestModel, ReadCategoryRequestModel
from app.schemas.category_response import CategoryResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.services.record_service import create_record
from app.services.category.category_read_service import read_category
from app.table.record import OperateType, EntityType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str

# ==================== Delete ====================
async def delete_category(
    request_model: DeleteCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    # 获取要删除的 category 信息
    result = await db.execute(
        select(Category).where(
            Category.id == uuid_to_str(request_model.category_id),
            Category.household_id == uuid_to_str(request_model.household_id)
        )
    )
    category = result.scalar_one_or_none()
    
    if category is None:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_40)
    
    category_name = cast(str, category.name)
    delete_ids = await _get_children_ids(request_model.category_id, db)
    
    if delete_ids:
        await db.execute(
            sql_delete(Category).where(Category.id.in_(delete_ids))
        )
        await db.flush()
    
    await _create_record(
        household_id=request_model.household_id,
        user_name=request_model.user_name,
        operate_type=OperateType.DELETE.value,
        category_name_old=category_name,
        db=db
    )
    
    return await read_category(
        ReadCategoryRequestModel(household_id=request_model.household_id),
        db
    )


# ==================== Private Method ====================

async def _get_children_ids(
    category_id: UUID,
    db: AsyncSession
) -> List[str]:
    delete_ids: List[str] = []
    
    async def match_children(current_id: str):
        delete_ids.append(current_id)
        
        result = await db.execute(
            select(Category.id).where(Category.parent_id == current_id)
        )
        child_ids = [row[0] for row in result.all()]
        
        for child_id in child_ids:
            await match_children(child_id)
    
    await match_children(uuid_to_str(category_id))
    return delete_ids

async def _create_record(
    household_id: UUID,
    user_name: str,
    operate_type: int,
    db: AsyncSession,
    category_name_old: Optional[str] = None,
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=household_id,
            user_name=user_name,
            operate_type=operate_type,
            entity_type=EntityType.CATEGORY.value,
            category_name_old=category_name_old,
        ),
        db
    )

