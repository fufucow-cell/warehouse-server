from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.category_model import Category
from app.schemas.warehouse_response import CategoryResponse
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
    parent_id: Optional[UUID] = Query(None, description="Parent Category ID"),
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
        user_id = get_user_id_from_header(request)
        if not user_id:
            return _error_handle(ServerErrorCode.UNAUTHORIZED_40)

        # 如果帶入 category_id，返回單筆分類詳細資料
        if category_id is not None:
            category = await _get_db_category(category_id, db)
            if not category:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
            
            response_data = CategoryResponse.model_validate(category).model_dump(
                mode="json",
                exclude_none=True,
            )
            return success_response(data=response_data)
        
        # 如果帶入 home_id，返回該家庭的所有分類
        if home_id is not None:
            categories = await _get_db_categories_by_home(home_id, level, parent_id, db)
            categories_data = [
                CategoryResponse.model_validate(category).model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for category in categories
            ]
            return success_response(data=categories_data)
        
        # 如果都沒有，返回錯誤
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)

    except SQLAlchemyError:
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception:
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
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.id == category_id)
    )
    return result.scalar_one_or_none()

# 獲取家庭的所有分類
async def _get_db_categories_by_home(
    home_id: int,
    level: Optional[int],
    parent_id: Optional[UUID],
    db: AsyncSession
) -> list[Category]:
    query = select(Category).where(Category.home_id == home_id)
    
    if level is not None:
        query = query.where(Category.level == level)
    
    if parent_id is not None:
        query = query.where(Category.parent_id == parent_id)
    elif level == 1:
        # 如果查詢第一層，parent_id 應該為 NULL
        query = query.where(Category.parent_id.is_(None))
    
    result = await db.execute(query)
    return list(result.scalars().all())

