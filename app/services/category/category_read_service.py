from typing import Optional, List, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table import Category
from app.schemas.category_request import ReadCategoryRequestModel
from app.schemas.category_response import CategoryResponseModel
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str

# ==================== Read ====================
async def read_category(
    request_model: ReadCategoryRequestModel,
    db: AsyncSession
) -> List[CategoryResponseModel]:
    query = select(Category).where(Category.household_id == uuid_to_str(request_model.household_id))
    
    if request_model.category_id is not None:
        query = query.where(Category.id == uuid_to_str(request_model.category_id))
        
    result = await db.execute(query)

    if request_model.category_id is not None:
        category = result.scalar_one_or_none()
        if not category:
            return []
            
        return await _get_ancestor_categories(category, db)
    else:
        categories = list(result.scalars().all())
        # 使用 build_category_tree 遞歸建立完整的樹結構（包含所有層級的子分類）
        return build_category_tree(categories)

# ==================== Public Method =====================

def gen_single_category_tree(categories: List[Category], category_id: UUID) -> Optional[CategoryResponseModel]:
    if not categories:
        return None

    # 先找出 category_id 的 category（使用 next() 找到第一個匹配的就立即返回，不會繼續遍歷）
    category_id_str = str(category_id)
    category = next((c for c in categories if c.id == category_id_str), None)
    if not category:
        return None
    
    cate_model = _convert_model(category)

    # 再找出 category 的 parent_id 的 category
    parent_category: Optional[Category] = None
    parent_cate_model: Optional[CategoryResponseModel] = None
    if category.parent_id:
        parent_id_str = str(category.parent_id)
        parent_category = next((c for c in categories if c.id == parent_id_str), None)
        if parent_category:
            parent_cate_model = _convert_model(parent_category)
            parent_cate_model.children = [cate_model]
    
    # 再找出 parent_category 的 parent_id 的 category（如果 parent_category 存在）
    grandparent_cate_model: Optional[CategoryResponseModel] = None
    if parent_category and parent_category.parent_id:
        grandparent_id_str = str(parent_category.parent_id)
        grandparent_category = next((c for c in categories if c.id == grandparent_id_str), None)
        if grandparent_category:
            grandparent_cate_model = _convert_model(grandparent_category)
            grandparent_cate_model.children = [parent_cate_model]
    
    if grandparent_cate_model:
        return grandparent_cate_model
    elif parent_cate_model:
        return parent_cate_model
    else:
        return cate_model

def build_category_tree(categories: List[Category]) -> List[CategoryResponseModel]:
    if not categories:
        return []
    
    first_level: List[CategoryResponseModel] = []
    remain: List[Category] = list(categories)
    
    # 第一遍：創建所有第一層級的 CategoryResponseModel 對象
    for category in list(remain):
        if category.parent_id is None:
            first_level.append(CategoryResponseModel(
                id=cast(UUID, category.id),
                name=cast(str, category.name),
                parent_id=cast(Optional[UUID], category.parent_id),
                children=[]
            ))
            remain.remove(category)
    
    # 遞歸建立父子關係，直到所有節點都被匹配完
    current_level = first_level
    while remain and current_level:
        current_level = _match_children_to_parents(current_level, remain)
    
    return first_level

async def get_level_names(
    category_id: Optional[UUID],
    db: AsyncSession
) -> List[str]:
    if category_id is None:
        return []
    
    result = await db.execute(
        select(Category).where(Category.id == uuid_to_str(category_id))
    )
    current = result.scalar_one_or_none()
    
    if not current:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    level_name: List[str] = []
    visited_ids = set()  # 用於檢測循環引用
    
    while current is not None:
        current_id = current.id
        # 檢測循環引用：如果當前 ID 已經訪問過，說明存在循環
        if current_id in visited_ids:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
        
        visited_ids.add(current_id)
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
    return build_category_tree(list(result.scalars().all()))

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
            # 將 category.parent_id (字符串) 和 model.id (UUID) 都轉換為字符串進行比較
            category_parent_id_str = str(category.parent_id)
            model_id_str = str(model.id)
            if category_parent_id_str == model_id_str:
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

def _convert_model(category: Category) -> CategoryResponseModel:
    return CategoryResponseModel(
        id=cast(UUID, category.id),
        name=cast(str, category.name),
        parent_id=cast(Optional[UUID], category.parent_id),
        children=[]
    )