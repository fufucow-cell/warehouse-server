from typing import Optional, List, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table import Category
from app.schemas.category_request import UpdateCategoryRequestModel
from app.schemas.record_request import CreateRecordRequestModel
from app.services.record_service import create_record
from app.services.category.category_read_service import get_level_names
from app.table.record import OperateType, EntityType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str, str_to_uuid

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))
MAX_LEVEL_NUM = 3

# ==================== Update ====================
async def update_category(
    request_model: UpdateCategoryRequestModel,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Category).where(
            Category.id == uuid_to_str(request_model.category_id),
            Category.household_id == uuid_to_str(request_model.household_id)
        )
    )
    category = result.scalar_one_or_none()

    if category is None:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_40)

    old_name = cast(str, category.name)
    old_parent_id = str_to_uuid(category.parent_id) if category.parent_id else None
    old_level_name = await get_level_names(
        category_id=old_parent_id,
        db=db
    )
    new_level_name = old_level_name.copy()
    old_level_name.append(old_name)
    is_name_changed = False
    is_parent_changed = False
    new_name = old_name
    
    # 處理 name 更新
    if request_model.name is not None:
        trimmed_name = request_model.name.strip()
        
        if len(trimmed_name) == 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)

        if trimmed_name != old_name:
            new_name = trimmed_name
            category.name = new_name
            is_name_changed = True
    
    # 處理 parent_id 更新
    if request_model.parent_id is None:
        new_level_name.append(new_name)
        pass
    elif request_model.parent_id == "" and category.parent_id is not None:
        category.parent_id = None
        new_level_name = [new_name]
        is_parent_changed = True
    else:
        # request_model.parent_id 是字符串，需要轉換為 UUID
        parent_id_uuid = str_to_uuid(request_model.parent_id)
        if parent_id_uuid is None:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
        
        # 驗證：parent_id 不能是自己的 category_id
        if parent_id_uuid == request_model.category_id:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
        
        # 驗證：parent_id 不能是自己的子分類（包括所有後代）
        all_children_ids = await _get_all_descendant_ids(category.id, db)
        parent_id_str = uuid_to_str(parent_id_uuid)
        if parent_id_str in all_children_ids:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
        
        new_level_name = await get_level_names(
            category_id=parent_id_uuid,
            db=db
        )
        category_level_num = await _get_children_max_level_num(category.id, db)

        if (category_level_num + len(new_level_name)) > MAX_LEVEL_NUM:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
        
        new_level_name.append(new_name)
        await _check_duplicate_category_name(
            household_id=request_model.household_id,
            name=new_name,
            parent_id=parent_id_uuid,
            db=db
        )
        category.parent_id = uuid_to_str(parent_id_uuid)
        is_parent_changed = True

    if not is_name_changed and not is_parent_changed:
        return
    
    category.updated_at = datetime.now(UTC_PLUS_8)
    await db.flush()
    await _gen_record(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.UPDATE.value,
            category_name_old=";".join(old_level_name),
            category_name_new=";".join(new_level_name),
            db=db
        )


# ==================== Private Method ====================

async def _check_duplicate_category_name(
    household_id: UUID,
    name: str,
    parent_id: Optional[UUID],
    db: AsyncSession
) -> None:
    duplicate_query = select(Category).where(
        Category.household_id == uuid_to_str(household_id),
        Category.name == name
    )
    if parent_id is not None:
        duplicate_query = duplicate_query.where(Category.parent_id == uuid_to_str(parent_id))
    else:
        duplicate_query = duplicate_query.where(Category.parent_id.is_(None))
    
    duplicate_result = await db.execute(duplicate_query)
    duplicate_category = duplicate_result.scalar_one_or_none()
    if duplicate_category:
        raise ValidationError(ServerErrorCode.CATEGORY_NAME_ALREADY_EXISTS_43)

async def _get_children_max_level_num(
    category_id: str,
    db: AsyncSession
) -> int:
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        return 0
    
    current_level = 1
    return await _check_children_level_recursive(category_id, current_level, db)

async def _get_all_descendant_ids(
    category_id: str,
    db: AsyncSession
) -> List[str]:
    """獲取分類的所有後代 ID（包括子分類、孫分類等）"""
    descendant_ids: List[str] = []
    
    async def collect_descendants(current_id: str):
        children_result = await db.execute(
            select(Category.id).where(Category.parent_id == current_id)
        )
        child_ids = [row[0] for row in children_result.all()]
        
        for child_id in child_ids:
            descendant_ids.append(child_id)
            await collect_descendants(child_id)
    
    await collect_descendants(category_id)
    return descendant_ids

async def _check_children_level_recursive(
    category_id: str,
    current_level: int,
    db: AsyncSession
) -> int:
    if current_level >= MAX_LEVEL_NUM:
        return MAX_LEVEL_NUM
    
    children_result = await db.execute(
        select(Category.id).where(Category.parent_id == category_id)
    )
    direct_children_ids = [row[0] for row in children_result.all()]
    
    if not direct_children_ids:
        return current_level
    
    max_child_level = current_level
    
    for child_id in direct_children_ids:
        child_level = await _check_children_level_recursive(child_id, current_level + 1, db)
        
        if child_level >= MAX_LEVEL_NUM:
            return MAX_LEVEL_NUM
        
        if child_level > max_child_level:
            max_child_level = child_level
    
    return max_child_level

async def _gen_record(
    household_id: UUID,
    user_name: str,
    operate_type: int,
    db: AsyncSession,
    category_name_old: Optional[str] = None,
    category_name_new: Optional[str] = None,
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=household_id,
            user_name=user_name,
            operate_type=operate_type,
            entity_type=EntityType.CATEGORY.value,
            category_name_old=category_name_old,
            category_name_new=category_name_new,
        ),
        db
    )

