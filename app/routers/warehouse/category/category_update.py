from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.category_model import Category
from app.schemas.warehouse_request import UpdateCategoryRequest
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
        await _update_db_category(request_data, db)
        
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
    
    # 如果提供了 parent_id，檢查父分類是否存在
    if request_data.parent_id is not None:
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
) -> None:
    result = await db.execute(
        select(Category).where(Category.id == request_data.category_id)
    )
    category = result.scalar_one()
    
    if request_data.name is not None:
        category.name = request_data.name
    if request_data.parent_id is not None:
        category.parent_id = request_data.parent_id
    if request_data.level is not None:
        category.level = request_data.level
    
    await db.commit()

