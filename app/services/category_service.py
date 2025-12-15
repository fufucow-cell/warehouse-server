from typing import Optional, List, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from app.table import Category
from app.schemas.category_request import CreateCategoryRequestModel, ReadCategoryRequestModel, UpdateCategoryRequestModel, DeleteCategoryRequestModel
from app.schemas.category_response import CategoryResponseModel
from app.utils.util_error_map import ServerErrorCode

# ==================== Create ====================
async def create_category(
    request_model: CreateCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    if request_model.parent_id is not None:
        parent_result = await db.execute(
            select(Category).where(Category.id == request_model.parent_id)
        )
        parent_category = parent_result.scalar_one_or_none()
        
        if not parent_category:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_40
        
        if parent_category.household_id != request_model.household_id:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_40
        
        new_level = parent_category.level + 1
        
        if new_level > 3:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_40
    else:
        new_level = 1
    
    new_category = Category(
        household_id=request_model.household_id,
        name=request_model.name,
        parent_id=request_model.parent_id,
        level=new_level
    )
    db.add(new_category)
    await db.flush()
    return await read_category(
        ReadCategoryRequestModel(household_id=request_model.household_id),
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
        raise ServerErrorCode.REQUEST_PATH_INVALID_40
    
    if request_model.name is not None:
        trimmed_name = request_model.name.strip()
        
        if len(trimmed_name) == 0:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_40

        category.name = trimmed_name
    
    await db.flush()

# ==================== Delete ====================
async def delete_category(
    request_model: DeleteCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    delete_ids = await _get_children_ids(request_model.category_id, db)
    
    if delete_ids:
        await db.execute(
            sql_delete(Category).where(Category.id.in_(delete_ids))
        )
        await db.flush()
    
    return await read_category(
        ReadCategoryRequestModel(household_id=request_model.household_id),
        db
    )


# ==================== Private Method ====================

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


def _build_category_tree(categories: List[Category]) -> List[CategoryResponseModel]:
    if not categories:
        return []
    
    first_level: List[CategoryResponseModel] = []
    second_level: List[CategoryResponseModel] = []
    remain: List[Category] = list(categories)
    
    # 第一遍：創建所有 CategoryResponseModel 對象
    for category in remain:
        if category.parent_id is None:
            first_level.append(CategoryResponseModel(
                id=category.id,
                name=category.name,
                parent_id=category.parent_id,
                level=category.level,
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
    for category in remain:
        if category.parent_id is not None:
            delete.append(category)
            continue
        for model in parents:
            if category.parent_id == model.id:
                model.children.append(CategoryResponseModel(
                    id=category.id,
                    name=category.name,
                    parent_id=category.parent_id,
                    level=category.level,
                    children=[]
                ))
                delete.append(category)
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