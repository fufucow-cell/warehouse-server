from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.item_model import Item
from app.models.cabinet_model import Cabinet
from app.schemas.warehouse_response import ItemResponse
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 路由入口
@router.get("/", response_class=JSONResponse)
async def fetch(
    request: Request,
    item_id: Optional[UUID] = Query(None, description="Item ID"),
    cabinet_id: Optional[UUID] = Query(None, description="Cabinet ID"),
    home_id: Optional[int] = Query(None, description="Home ID"),
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
        user_id = get_user_id_from_header(request)
        if not user_id:
            return _error_handle(ServerErrorCode.UNAUTHORIZED_40)

        # 如果帶入 item_id，返回單筆物品詳細資料
        if item_id is not None:
            item = await _get_db_item(item_id, db)
            if not item:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
            
            response_data = ItemResponse.model_validate(item).model_dump(
                mode="json",
                exclude_none=True,
            )
            return success_response(data=response_data)
        
        # 如果帶入 cabinet_id，返回該櫥櫃的所有物品
        if cabinet_id is not None:
            items = await _get_db_items_by_cabinet(cabinet_id, db)
            items_data = [
                ItemResponse.model_validate(item).model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for item in items
            ]
            return success_response(data=items_data)
        
        # 如果帶入 home_id，返回該家庭的所有物品
        if home_id is not None:
            items = await _get_db_items_by_home(home_id, db)
            items_data = [
                ItemResponse.model_validate(item).model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for item in items
            ]
            return success_response(data=items_data)
        
        # 如果都沒有，返回錯誤
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)

    except SQLAlchemyError:
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception:
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 獲取單筆物品
async def _get_db_item(
    item_id: UUID,
    db: AsyncSession
) -> Optional[Item]:
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.categories))
        .where(Item.id == item_id)
    )
    return result.scalar_one_or_none()

# 獲取櫥櫃的所有物品
async def _get_db_items_by_cabinet(
    cabinet_id: UUID,
    db: AsyncSession
) -> list[Item]:
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.categories))
        .where(Item.cabinet_id == cabinet_id)
    )
    return list(result.scalars().all())

# 獲取家庭的所有物品
async def _get_db_items_by_home(
    home_id: int,
    db: AsyncSession
) -> list[Item]:
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.categories))
        .where(Item.home_id == home_id)
    )
    return list(result.scalars().all())

