from typing import Optional, List, Dict, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from app.table import Category
from app.schemas.category_request import CreateCategoryRequestModel, ReadCategoryRequestModel, UpdateCategoryRequestModel, DeleteCategoryRequestModel
from app.schemas.category_response import CategoryResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.services.record_service import create_record
from app.table.record import OperateType, EntityType, RecordType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))
MAX_LEVEL_NUM = 3

# ==================== Create ====================
async def create_category(
    request_model: CreateCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    level_name = await get_level_names(
        category_id=request_model.parent_id,
        db=db
    )
    level_name.append(request_model.name)

    if len(level_name) > MAX_LEVEL_NUM:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    await _check_duplicate_category_name(
        household_id=request_model.household_id,
        name=request_model.name,
        parent_id=request_model.parent_id,
        db=db
    )
    
    now_utc8 = datetime.now(UTC_PLUS_8)
    new_category = Category(
        household_id=request_model.household_id,
        name=request_model.name,
        parent_id=request_model.parent_id,
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


# ==================== Read ====================
async def read_category(
    request_model: ReadCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    query = select(Category).where(Category.household_id == request_model.household_id)
    
    if request_model.category_id is not None:
        query = query.where(Category.id == request_model.category_id)
        
    result = await db.execute(query)

    if request_model.category_id is not None:
        category = result.scalar_one_or_none()
        if not category:
            return []
            
        return await _get_ancestor_categories(category, db)
    else:
        categories = list(result.scalars().all())
        return _build_category_tree(categories)


# ==================== Update ====================
async def update_category(
    request_model: UpdateCategoryRequestModel,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Category).where(
            Category.id == request_model.category_id,
            Category.household_id == request_model.household_id
        )
    )
    category = result.scalar_one_or_none()

    if category is None:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_40)

    old_name = cast(str, category.name)
    old_level_name = await get_level_names(
        category_id=category.parent_id,
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
    
    # 處理 pareint_id 更新
    if request_model.parent_id is None:
        new_level_name.append(new_name)
        pass
    elif request_model.parent_id == "" and category.parent_id is not None:
        if category.parent_id is not None:
            category.parent_id = None
            new_level_name = [new_name]
            is_parent_changed = True
    else:
        new_level_name = await get_level_names(
            category_id=request_model.parent_id,
            db=db
        )
        category_level_num = await _get_children_max_level_num(category.id, db)

        if (category_level_num + len(new_level_name)) > MAX_LEVEL_NUM:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
        
        new_level_name.append(new_name)
        await _check_duplicate_category_name(
            household_id=request_model.household_id,
            name=new_name,
            parent_id=request_model.parent_id,
            db=db
        )
        category.parent_id = request_model.parent_id
        is_parent_changed = True

    if not is_name_changed and not is_parent_changed:
        return
    
    category.updated_at = datetime.now(UTC_PLUS_8)
    await db.flush()
    await _create_record(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.UPDATE.value,
            category_name_old=";".join(old_level_name),
            category_name_new=";".join(new_level_name),
            db=db
        )
        

# ==================== Delete ====================
async def delete_category(
    request_model: DeleteCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    # 获取要删除的 category 信息
    result = await db.execute(
        select(Category).where(
            Category.id == request_model.category_id,
            Category.household_id == request_model.household_id
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

async def _create_record(
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
            record_type=RecordType.NORMAL.value,
            category_name_old=category_name_old,
            category_name_new=category_name_new,
        ),
        db
    )

async def get_level_names(
    category_id: Optional[UUID],
    db: AsyncSession
) -> List[str]:
    if category_id is None:
        return []
    
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    current = result.scalar_one_or_none()
    
    if not current:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    level_name: List[str] = []
    while current is not None:
        level_name.insert(0, cast(str, current.name))
        if current.parent_id is None:
            break
        
        result = await db.execute(
            select(Category).where(Category.id == current.parent_id)
        )
        current = result.scalar_one_or_none()
        if not current:
            break
    
    return level_name

# 檢查同一個 parent_id 下，不能有相同的名字
async def _check_duplicate_category_name(
    household_id: UUID,
    name: str,
    parent_id: Optional[UUID],
    db: AsyncSession
) -> None:
    duplicate_query = select(Category).where(
        Category.household_id == household_id,
        Category.name == name
    )
    if parent_id is not None:
        duplicate_query = duplicate_query.where(Category.parent_id == parent_id)
    else:
        duplicate_query = duplicate_query.where(Category.parent_id.is_(None))
    
    duplicate_result = await db.execute(duplicate_query)
    duplicate_category = duplicate_result.scalar_one_or_none()
    if duplicate_category:
        raise ValidationError(ServerErrorCode.CATEGORY_NAME_ALREADY_EXISTS_43)

async def _get_ancestor_categories(
    category: Category,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    ancestor_ids = {category.id}
    
    # 收集所有祖先
    current = category
    while current.parent_id is not None:
        ancestor_ids.add(current.parent_id)
        parent_result = await db.execute(
            select(Category).where(
                Category.id == current.parent_id,
                Category.household_id == category.household_id
            )
        )
        current = parent_result.scalar_one_or_none()
        if not current:
            break
    
    result = await db.execute(
            select(Category).where(
                Category.id.in_(ancestor_ids),
                Category.household_id == category.household_id
            )
        )
    return _build_category_tree(list(result.scalars().all()))

# 取得 children 的最大層級數
async def _get_children_max_level_num(
    category_id: UUID,
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


async def _check_children_level_recursive(
    category_id: UUID,
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

def _build_category_tree(categories: List[Category]) -> List[CategoryResponseModel]:
    if not categories:
        return []
    
    first_level: List[CategoryResponseModel] = []
    second_level: List[CategoryResponseModel] = []
    remain: List[Category] = list(categories)
    
    # 第一遍：創建所有 CategoryResponseModel 對象
    for category in list(remain):
        if category.parent_id is None:
            first_level.append(CategoryResponseModel(
                id=cast(UUID, category.id),
                name=cast(str, category.name),
                parent_id=cast(Optional[UUID], category.parent_id),
                children=[]
            ))
            remain.remove(category)
    
    # 建立父子關係（遞歸處理所有層級）
    second_level = _match_children_to_parents(first_level, remain)
    _match_children_to_parents(second_level, remain)
    return first_level


def _match_children_to_parents(
    parents: List[CategoryResponseModel],
    remain: List[Category]
) -> List[CategoryResponseModel]:
    delete = []
    result = []
    for category in list(remain):
        if category.parent_id is None:
            continue
        matched = False
        for model in parents:
            if category.parent_id == model.id:
                child_model = CategoryResponseModel(
                    id=cast(UUID, category.id),
                    name=cast(str, category.name),
                    parent_id=cast(Optional[UUID], category.parent_id),
                    children=[]
                )
                model.children.append(child_model)
                result.append(child_model)
                delete.append(category)
                matched = True
                break
    
    for category in delete:
        remain.remove(category)
    
    return result

async def _get_children_ids(
    category_id: UUID,
    db: AsyncSession
) -> List[UUID]:
    delete_ids: List[UUID] = []
    
    async def match_children(current_id: UUID):
        delete_ids.append(current_id)
        
        result = await db.execute(
            select(Category.id).where(Category.parent_id == current_id)
        )
        child_ids = [row[0] for row in result.all()]
        
        for child_id in child_ids:
            await match_children(child_id)
    
    await match_children(category_id)
    return delete_ids