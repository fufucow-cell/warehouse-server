from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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

    except SQLAlchemyError:
        if db.in_transaction():
            await db.rollback()
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception:
        if db.in_transaction():
            await db.rollback()
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
    
    return None

# 刪除分類資料
async def _delete_db_category(
    request_data: DeleteCategoryRequest,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Category).where(Category.id == request_data.category_id)
    )
    category = result.scalar_one()
    await db.delete(category)
    await db.commit()

