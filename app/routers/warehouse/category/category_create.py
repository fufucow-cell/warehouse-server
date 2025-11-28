from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.category_model import Category
from app.schemas.warehouse_request import CreateCategoryRequest
from app.schemas.warehouse_response import CategoryResponse
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 路由入口
@router.post("/", response_class=JSONResponse)
async def create(
    request_data: CreateCategoryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查（parent_id 的空字串已在 schema validator 中處理為 None）
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 創建分類資料
        new_category = await _create_db_category(request_data, db)
        
        # 產生響應資料（手動構建，避免觸發 SQLAlchemy relationship 懶加載）
        # 不包含 home_id 和 parent_id
        response_data = {
            "id": str(new_category.id),
            "name": new_category.name,
            "level": new_category.level
            # 不包含 children（新創建的分類沒有子分類）
        }
        return success_response(data=response_data)

    except SQLAlchemyError as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SQLAlchemyError in create category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exception in create category: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: CreateCategoryRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.name or not request_data.name.strip():
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_40)
    
    # 如果提供了 parent_id，檢查父分類是否存在
    if request_data.parent_id:
        result = await db.execute(
            select(Category).where(Category.id == request_data.parent_id)
        )
        parent_category = result.scalar_one_or_none()
        if not parent_category:
            return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
        
        # 檢查層級是否正確（子分類的 level 應該是父分類的 level + 1）
        if request_data.level != parent_category.level + 1:
            return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    else:
        # 如果沒有 parent_id，level 必須是 1
        if request_data.level != 1:
            return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    # 檢查同一 level 下是否已存在相同名稱的分類
    # 在同一个 home_id 下，同一个 level，同一个 parent_id（或都是 NULL）下，name 不能重复
    query = select(Category).where(
        Category.home_id == request_data.home_id,
        Category.level == request_data.level,
        Category.name == request_data.name.strip()
    )
    
    # 如果 parent_id 存在，检查同一 parent_id 下是否有相同 name
    # 如果 parent_id 为 NULL，检查同一 home_id、同一 level、parent_id 为 NULL 下是否有相同 name
    if request_data.parent_id:
        query = query.where(Category.parent_id == request_data.parent_id)
    else:
        query = query.where(Category.parent_id.is_(None))
    
    result = await db.execute(query)
    existing_category = result.scalar_one_or_none()
    if existing_category:
            return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)

    return None

# 創建分類資料
async def _create_db_category(
    request_data: CreateCategoryRequest,
    db: AsyncSession
) -> Category:
    """創建分類資料"""
    new_category = Category(
        home_id=request_data.home_id,
        name=request_data.name,
        parent_id=request_data.parent_id,
        level=request_data.level
    )
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)
    return new_category

