from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.category_model import Category
from app.schemas.warehouse_request import UpdateCategoryRequest
from app.schemas.warehouse_response import CategoryResponse
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 路由入口
@router.put("/", response_class=JSONResponse)
async def update(
    request_data: UpdateCategoryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 修改分類資料
        updated_category = await _update_db_category(request_data, db)
        
        # 產生響應資料（返回更新後的分類資訊）
        response_data = {
            "id": str(updated_category.id),
            "name": updated_category.name,
            "level": updated_category.level
        }
        # 如果 level > 1 且有 parent_id，添加 parent_id
        if updated_category.level > 1 and updated_category.parent_id is not None:
            response_data["parent_id"] = str(updated_category.parent_id)
        
        return success_response(data=response_data)

    except ValueError as e:
        if db.in_transaction():
            await db.rollback()
        # ValueError 通常是驗證錯誤（如子分類 level 超過 3）
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    except SQLAlchemyError as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SQLAlchemyError in update category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exception in update category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: UpdateCategoryRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.category_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    if request_data.name is not None and not request_data.name.strip():
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_40)
    
    # 檢查 Category 是否存在
    result = await db.execute(
        select(Category).where(Category.id == request_data.category_id)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
    
    # 驗證 category 的 home_id 是否與請求中的 home_id 匹配
    if category.home_id != request_data.home_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    # 如果更新到 level 1，忽略 parent_id 條件（level 1 的分類沒有父分類）
    # 如果提供了 parent_id 且 level 不是 1，檢查父分類是否存在
    if request_data.parent_id is not None:
        # 確定要使用的 level（如果提供了新的 level，使用新的；否則使用當前的）
        target_level = request_data.level if request_data.level is not None else category.level
        
        # 如果目標 level 是 1，忽略 parent_id 驗證（level 1 不應該有 parent_id）
        if target_level == 1:
            # level 1 時，parent_id 應該為 None，這裡不驗證 parent_id
            pass
        else:
            # level > 1 時，驗證 parent_id 是否存在
            parent_result = await db.execute(
                select(Category).where(Category.id == request_data.parent_id)
            )
            parent_category = parent_result.scalar_one_or_none()
            if not parent_category:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
    
    return None

# 修改分類資料
async def _update_db_category(
    request_data: UpdateCategoryRequest,
    db: AsyncSession
) -> Category:
    result = await db.execute(
        select(Category).where(Category.id == request_data.category_id)
    )
    category = result.scalar_one()
    
    if request_data.name is not None:
        category.name = request_data.name
    
    # 處理 level 和 parent_id 的更新
    old_level = category.level
    if request_data.level is not None:
        new_level = request_data.level
        level_diff = new_level - old_level  # 計算 level 的變化量
        
        # 如果 level 發生變化，先檢查子分類的 level 是否會超過 3
        if level_diff != 0:
            max_child_level = await _get_max_child_level(category.id, db)
            if max_child_level is not None:
                new_max_child_level = max_child_level + level_diff
                if new_max_child_level > 3:
                    # 子分類的 level 會超過 3，返回錯誤
                    raise ValueError(f"無法更新：子分類的 level 會超過 3（當前最大子分類 level: {max_child_level}，更新後會變成: {new_max_child_level}）")
        
        category.level = new_level
        # 如果更新到 level 1，parent_id 必須為 None（level 1 沒有父分類）
        if new_level == 1:
            category.parent_id = None
        elif request_data.parent_id is not None:
            # 如果更新到 level > 1 且提供了 parent_id，使用提供的 parent_id
            category.parent_id = request_data.parent_id
        
        # 如果 level 發生變化，遞歸更新所有子分類的 level
        if level_diff != 0:
            await _update_children_level(category.id, level_diff, db)
    elif request_data.parent_id is not None:
        # 如果沒有更新 level，但提供了 parent_id，使用提供的 parent_id
        # 但需要確保當前 level > 1（level 1 不應該有 parent_id）
        if category.level == 1:
            # 如果當前是 level 1，忽略 parent_id（level 1 不應該有 parent_id）
            pass
        else:
            category.parent_id = request_data.parent_id
    
    await db.commit()
    await db.refresh(category)
    
    return category


async def _get_max_child_level(
    parent_id: UUID,
    db: AsyncSession
) -> Optional[int]:
    """
    獲取指定分類的所有子分類中的最大 level
    
    Args:
        parent_id: 父分類 ID
        db: 數據庫會話
    
    Returns:
        Optional[int]: 最大子分類 level，如果沒有子分類返回 None
    """
    max_level = None
    
    async def find_max_level(current_parent_id: UUID):
        nonlocal max_level
        # 查找所有直接子分類
        result = await db.execute(
            select(Category).where(Category.parent_id == current_parent_id)
        )
        children = result.scalars().all()
        
        for child in children:
            # 更新最大 level
            if max_level is None or child.level > max_level:
                max_level = child.level
            
            # 遞歸查找子分類的子分類
            await find_max_level(child.id)
    
    await find_max_level(parent_id)
    return max_level


async def _update_children_level(
    parent_id: UUID,
    level_diff: int,
    db: AsyncSession
) -> None:
    """
    遞歸更新所有子分類的 level
    
    Args:
        parent_id: 父分類 ID
        level_diff: level 的變化量（例如：從 level 2 變成 level 1，level_diff = -1）
        db: 數據庫會話
    """
    # 查找所有直接子分類
    result = await db.execute(
        select(Category).where(Category.parent_id == parent_id)
    )
    children = result.scalars().all()
    
    # 遞歸更新每個子分類
    for child in children:
        new_level = child.level + level_diff
        
        # 確保 level 在有效範圍內（1-3）
        if new_level < 1:
            new_level = 1
        elif new_level > 3:
            new_level = 3
        
        child.level = new_level
        
        # 如果子分類變成了 level 1，parent_id 必須為 None
        if new_level == 1:
            child.parent_id = None
        
        # 遞歸更新子分類的子分類
        await _update_children_level(child.id, level_diff, db)

