from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.item_model import Item, ItemCategory
from app.models.category_model import Category
from app.schemas.warehouse_request import UpdateItemRequest
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 路由入口
@router.put("/", response_class=JSONResponse)
async def update(
    request_data: UpdateItemRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 修改物品資料
        await _update_db_item(request_data, db)
        
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
    request_data: UpdateItemRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.item_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    if request_data.name is not None and not request_data.name.strip():
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_40)
    
    # 檢查 Item 是否存在
    result = await db.execute(
        select(Item).where(Item.id == request_data.item_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
    
    # 檢查分類是否存在（如果提供了分類）
    if request_data.category_ids:
        for category_id in request_data.category_ids:
            result = await db.execute(
                select(Category).where(Category.id == category_id)
            )
            category = result.scalar_one_or_none()
            if not category:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
    
    return None

# 修改物品資料
async def _update_db_item(
    request_data: UpdateItemRequest,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Item).where(Item.id == request_data.item_id)
    )
    item = result.scalar_one()
    
    if request_data.room_id is not None:
        item.room_id = request_data.room_id
    if request_data.home_id is not None:
        item.home_id = request_data.home_id
    if request_data.name is not None:
        item.name = request_data.name
    if request_data.description is not None:
        item.description = request_data.description
    if request_data.quantity is not None:
        item.quantity = request_data.quantity
    if request_data.min_stock_alert is not None:
        item.min_stock_alert = request_data.min_stock_alert
    if request_data.photo is not None:
        item.photo = request_data.photo
    
    # 更新分類關聯（如果提供了分類）
    if request_data.category_ids is not None:
        # 刪除現有的分類關聯
        await db.execute(
            delete(ItemCategory).where(ItemCategory.item_id == request_data.item_id)
        )
        # 添加新的分類關聯
        for category_id in request_data.category_ids:
            item_category = ItemCategory(
                item_id=request_data.item_id,
                category_id=category_id
            )
            db.add(item_category)
    
    await db.commit()

