from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import delete as sql_delete
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.category_model import Category
from app.schemas.warehouse_request import DeleteCategoryRequest
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 路由入口
@router.delete("/", response_class=JSONResponse)
async def delete(
    request_data: DeleteCategoryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 刪除分類資料
        await _delete_db_category(request_data, db)
        
        # 產生響應資料（不返回 data）
        return success_response()

    except SQLAlchemyError as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SQLAlchemyError in delete category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exception in delete category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: DeleteCategoryRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.category_id:
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
    
    return None

# 刪除分類資料
async def _delete_db_category(
    request_data: DeleteCategoryRequest,
    db: AsyncSession
) -> None:
    """
    刪除分類資料（遞歸刪除所有子分類）
    先遞歸刪除所有子分類，再刪除父分類
    這樣可以確保即使數據庫 CASCADE 約束未生效，也能正確刪除所有相關分類
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 遞歸獲取所有需要刪除的分類 ID（包括自身和所有子分類）
    category_ids_to_delete = await _get_all_descendant_ids(request_data.category_id, db)
    
    logger.info(f"準備刪除 {len(category_ids_to_delete)} 個分類: {[str(cid) for cid in category_ids_to_delete]}")
    
    # 刪除所有相關分類（包括自身和所有子分類）
    if category_ids_to_delete:
        try:
            # 使用批量刪除
            # 注意：由於數據庫有 CASCADE 約束，刪除父分類會自動刪除子分類
            # 但為了確保，我們還是先收集所有需要刪除的 ID
            result = await db.execute(
                sql_delete(Category).where(Category.id.in_(category_ids_to_delete))
            )
            deleted_count = result.rowcount
            await db.commit()
            logger.info(f"成功刪除 {deleted_count} 個分類")
        except Exception as e:
            await db.rollback()
            logger.error(f"刪除分類時發生錯誤: {e}", exc_info=True)
            logger.error(f"嘗試刪除的分類 ID: {[str(cid) for cid in category_ids_to_delete]}")
            raise


async def _get_all_descendant_ids(
    category_id: UUID,
    db: AsyncSession
) -> List[UUID]:
    """
    遞歸獲取指定分類及其所有子分類的 ID
    
    Args:
        category_id: 要刪除的分類 ID (UUID)
        db: 數據庫會話
    
    Returns:
        List[UUID]: 包含自身和所有子分類 ID 的列表
    """
    category_ids_to_delete: List[UUID] = []
    
    # 遞歸函數：獲取分類及其所有子分類
    async def collect_descendants(current_id: UUID):
        # 將當前分類 ID 加入列表
        category_ids_to_delete.append(current_id)
        
        # 查找所有子分類
        result = await db.execute(
            select(Category.id).where(Category.parent_id == current_id)
        )
        child_ids = [row[0] for row in result.all()]
        
        # 遞歸處理每個子分類
        for child_id in child_ids:
            await collect_descendants(child_id)
    
    # 開始遞歸收集
    await collect_descendants(category_id)
    
    return category_ids_to_delete
