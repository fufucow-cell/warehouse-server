from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.table.item_model import Item
from app.schemas.item_request import DeleteItemRequestModel
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header
from app.utils.util_file import delete_uploaded_file
from app.utils.util_log import create_log
from app.table.log_model import StateType, ItemType, LogType
import logging

router = APIRouter()

# 路由入口
@router.delete("/", response_class=JSONResponse)
async def delete(
    request_data: DeleteItemRequestModel,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 獲取 item 信息（用於記錄 log）
        result = await db.execute(
            select(Item).where(Item.id == request_data.item_id)
        )
        item = result.scalar_one()
        household_id = item.household_id
        
        # 刪除物品資料
        await _delete_db_item(request_data, db)
        
        # 建立操作日誌
        log_result = await create_log(
            db=db,
            home_id=household_id,
            state=StateType.DELETE,
            item_type=ItemType.ITEM,
            user_name=request_data.user_name,
            operate_type=None,  # delete 操作不需要 operate_type
            log_type=LogType.NORMAL,
        )
        if not log_result:
            logging.getLogger(__name__).warning("Failed to create item log for item_id=%s", str(request_data.item_id))
        
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
    request_data: DeleteItemRequestModel,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.item_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    if not request_data.household_id:
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
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    # 驗證物品是否屬於該家庭
    if item.household_id != request_data.household_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)
    
    return None

# 刪除物品資料
async def _delete_db_item(
    request_data: DeleteItemRequestModel,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Item).where(Item.id == request_data.item_id)
    )
    item = result.scalar_one()
    
    # 刪除對應的圖片文件（如果存在）
    if item.photo:
        delete_uploaded_file(item.photo)
    
    await db.delete(item)
    await db.commit()

