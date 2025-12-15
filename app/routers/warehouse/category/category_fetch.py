from typing import Optional, List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.table.category_model import Category
from app.schemas.category_response import CategoryResponseModel
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 路由入口
@router.get("/", response_class=JSONResponse)
async def fetch(
    request: Request,
    category_id: Optional[UUID] = Query(None, description="Category ID"),
    home_id: Optional[int] = Query(None, description="Home ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="分类层级"),
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
        user_id = get_user_id_from_header(request)
        if not user_id:
            return _error_handle(ServerErrorCode.UNAUTHORIZED_40)

        # 如果指定了 level，返回扁平化列表（不構建層級結構）
        if level is not None:
            if category_id is not None:
                # 如果同時指定了 category_id 和 level
                # 獲取該分類及其所有子分類，然後篩選出該 level 的分類
                category = await _get_db_category(category_id, db)
                if not category:
                    return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
                
                # 獲取該分類及其所有子分類（遞歸）
                all_related_categories = await _get_category_with_children(category_id, db)
                
                # 篩選出該 level 的分類
                filtered_categories = [
                    cat for cat in all_related_categories if cat.level == level
                ]
                
                # 轉換為扁平化列表
                # 如果 level > 1，包含 parent_id
                categories_data = []
                for cat in filtered_categories:
                    category_data = {
                        "id": str(cat.id),
                        "name": cat.name,
                        "level": cat.level
                    }
                    # 如果 level > 1，添加 parent_id
                    if level > 1 and cat.parent_id is not None:
                        category_data["parent_id"] = str(cat.parent_id)
                    categories_data.append(category_data)
                
                return success_response(data=categories_data)
            elif home_id is not None:
                # 如果指定了 home_id 和 level，返回該家庭該 level 的所有分類（扁平化）
                categories = await _get_db_categories_by_home(home_id, level, db)
                # 如果 level > 1，包含 parent_id
                categories_data = []
                for cat in categories:
                    category_data = {
                        "id": str(cat.id),
                        "name": cat.name,
                        "level": cat.level
                    }
                    # 如果 level > 1，添加 parent_id
                    if level > 1 and cat.parent_id is not None:
                        category_data["parent_id"] = str(cat.parent_id)
                    categories_data.append(category_data)
                return success_response(data=categories_data)
            else:
                # 如果只指定了 level，返回所有該 level 的分類（扁平化）
                categories = await _get_all_categories(level, db)
                # 如果 level > 1，包含 parent_id
                categories_data = []
                for cat in categories:
                    category_data = {
                        "id": str(cat.id),
                        "name": cat.name,
                        "level": cat.level
                    }
                    # 如果 level > 1，添加 parent_id
                    if level > 1 and cat.parent_id is not None:
                        category_data["parent_id"] = str(cat.parent_id)
                    categories_data.append(category_data)
                return success_response(data=categories_data)
        
        # 如果沒有指定 level，構建層級結構
        # 如果帶入 category_id，返回該分類自身及所有下級分類
        if category_id is not None:
            category = await _get_db_category(category_id, db)
            if not category:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
            
            # 獲取該分類及其所有子分類（遞歸）
            all_related_categories = await _get_category_with_children(category_id, db)
            
            # 構建層級結構（以該分類為根）
            categories_data = _build_category_tree_from_root(all_related_categories, category_id)
            
            return success_response(data=categories_data)
        
        # 如果帶入 home_id，返回該家庭的所有分類（構建層級結構）
        if home_id is not None:
            # 為了構建完整的層級結構，先獲取所有分類
            all_categories = await _get_db_categories_by_home(home_id, None, db)
            # 構建層級結構
            categories_data = _build_category_tree(all_categories)
            
            return success_response(data=categories_data)
        
        # 如果都沒有帶參數，返回所有分類（構建層級結構）
        # 獲取所有分類
        all_categories = await _get_all_categories(None, db)
        # 構建層級結構
        categories_data = _build_category_tree(all_categories)
        
        return success_response(data=categories_data)

    except SQLAlchemyError as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SQLAlchemyError in fetch category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exception in fetch category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 獲取單筆分類
async def _get_db_category(
    category_id: UUID,
    db: AsyncSession
) -> Optional[Category]:
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    return result.scalar_one_or_none()


async def _get_category_with_children(
    category_id: UUID,
    db: AsyncSession
) -> List[Category]:
    """
    獲取分類及其所有子分類（遞歸）
    
    Args:
        category_id: 分類 ID
        db: 數據庫會話
    
    Returns:
        List[Category]: 包含該分類及其所有子分類的列表
    """
    # 先獲取該分類
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    root_category = result.scalar_one_or_none()
    
    if not root_category:
        return []
    
    # 獲取該分類的 home_id，然後獲取該家庭的所有分類
    # 這樣可以獲取所有可能相關的分類
    all_categories_result = await db.execute(
        select(Category).where(Category.home_id == root_category.home_id)
    )
    all_categories = list(all_categories_result.scalars().all())
    
    # 過濾出該分類及其所有子分類
    related_categories = []
    category_ids_to_include = {category_id}
    
    # 遞歸查找所有子分類
    def find_children(parent_id: UUID):
        for cat in all_categories:
            if cat.parent_id == parent_id:
                category_ids_to_include.add(cat.id)
                find_children(cat.id)
    
    find_children(category_id)
    
    # 只返回相關的分類
    for cat in all_categories:
        if cat.id in category_ids_to_include:
            related_categories.append(cat)
    
    return related_categories


def _build_category_tree_from_root(
    categories: List[Category],
    root_category_id: UUID
) -> dict:
    """
    從指定分類開始構建層級結構
    
    Args:
        categories: 分類列表（包含根分類及其所有子分類）
        root_category_id: 根分類 ID
    
    Returns:
        dict: 以指定分類為根的層級結構
    """
    if not categories:
        return {}
    
    # 將分類轉換為字典
    category_dict: Dict[UUID, dict] = {}
    root_category_data = None
    
    for category in categories:
        category_data = {
            "id": str(category.id),
            "name": category.name,
            "level": category.level,
            "children": []
        }
        category_dict[category.id] = category_data
        
        if category.id == root_category_id:
            root_category_data = category_data
    
    if not root_category_data:
        return {}
    
    # 構建層級關係：將子分類添加到父分類的 children 中
    for category in categories:
        if category.parent_id is not None and category.parent_id in category_dict:
            parent_data = category_dict[category.parent_id]
            child_data = category_dict[category.id]
            parent_data["children"].append(child_data)
    
    # 清理空的 children 字段
    def remove_empty_children(cat: dict) -> None:
        """遞歸移除空的 children 字段"""
        if "children" in cat:
            # 如果有子分類，遞歸處理子分類
            if cat["children"]:
                for child in cat["children"]:
                    remove_empty_children(child)
                # 如果處理後 children 為空，移除該字段
                if len(cat["children"]) == 0:
                    cat.pop("children", None)
            else:
                # 如果 children 為空，直接移除
                cat.pop("children", None)
    
    remove_empty_children(root_category_data)
    
    return root_category_data

# 獲取家庭的所有分類
async def _get_db_categories_by_home(
    home_id: int,
    level: Optional[int],
    db: AsyncSession
) -> list[Category]:
    query = select(Category).where(Category.home_id == home_id)
    
    if level is not None:
        query = query.where(Category.level == level)
    
    result = await db.execute(query)
    return list(result.scalars().all())


# 獲取所有分類
async def _get_all_categories(
    level: Optional[int],
    db: AsyncSession
) -> list[Category]:
    """獲取所有分類（不限 home_id）"""
    query = select(Category)
    
    if level is not None:
        query = query.where(Category.level == level)
    
    result = await db.execute(query)
    return list(result.scalars().all())


def _build_category_tree(categories: List[Category], max_level: Optional[int] = None) -> List[dict]:
    """
    構建分類的層級結構（樹形結構）
    
    Args:
        categories: 分類列表（扁平化）
        max_level: 最大顯示層級（如果指定，只顯示到該層級，不顯示更深層的子分類）
    
    Returns:
        List[dict]: 層級結構的分類列表（只包含第一層分類，子分類在 children 中）
    """
    if not categories:
        return []
    
    # 將分類轉換為字典，並按 level 分組
    category_dict: Dict[UUID, dict] = {}
    level_1_categories: List[dict] = []
    
    # 先將所有分類轉換為字典（手動構建，避免觸發 SQLAlchemy relationship）
    for category in categories:
        # 手動構建字典，避免使用 model_validate 觸發 relationship 懶加載
        # 不包含 home_id 和 parent_id
        category_data = {
            "id": str(category.id),
            "name": category.name,
            "level": category.level,
            "children": []  # 初始化 children 列表
        }
        category_dict[category.id] = category_data
        
        # 如果是第一層分類（parent_id 為 None），加入根列表
        if category.parent_id is None:
            level_1_categories.append(category_data)
    
    # 構建層級關係：將子分類添加到父分類的 children 中
    # 如果指定了 max_level，只構建到該層級
    for category in categories:
        if category.parent_id is not None and category.parent_id in category_dict:
            # 如果指定了 max_level，檢查是否超過最大層級
            if max_level is not None and category.level > max_level:
                continue
            
            # 找到父分類，將當前分類添加到父分類的 children 中
            parent_data = category_dict[category.parent_id]
            child_data = category_dict[category.id]
            parent_data["children"].append(child_data)
    
    # 清理空的 children 字段
    def remove_empty_children(cat_list: List[dict]) -> None:
        """遞歸移除空的 children 字段"""
        for cat in cat_list:
            # 檢查是否有 children 字段
            if "children" in cat:
                # 如果有子分類，遞歸處理子分類
                if cat["children"]:
                    remove_empty_children(cat["children"])
                    # 如果處理後 children 為空，移除該字段
                    if len(cat["children"]) == 0:
                        cat.pop("children", None)
                else:
                    # 如果 children 為空，直接移除
                    cat.pop("children", None)
    
    # 移除所有空的 children 字段
    remove_empty_children(level_1_categories)
    
    # 返回第一層分類（包含所有子分類）
    return level_1_categories


def _filter_category_tree(
    categories: List[dict],
    level: Optional[int]
) -> List[dict]:
    """
    過濾分類樹（根據 level）
    
    Args:
        categories: 分類樹
        level: 要過濾的層級
    
    Returns:
        List[dict]: 過濾後的分類樹
    """
    if level is None:
        return categories
    
    def filter_recursive(cat_list: List[dict]) -> List[dict]:
        filtered = []
        for cat in cat_list:
            # 檢查是否符合過濾條件（根據 level）
            match = cat.get("level") == level
            
            # 遞歸過濾子分類
            if cat.get("children"):
                cat["children"] = filter_recursive(cat["children"])
            
            # 如果當前分類符合條件，或者有符合條件的子分類，則保留
            if match or (cat.get("children") and len(cat["children"]) > 0):
                filtered.append(cat)
        
        return filtered
    
    return filter_recursive(categories)

