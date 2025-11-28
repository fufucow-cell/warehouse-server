from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.cabinet_model import Cabinet
from app.schemas.warehouse_request import DeleteCabinetRequest
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header
from app.utils.util_log import create_log
from app.models.log_model import StateType, ItemType, LogType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 路由入口
@router.delete("/", response_class=JSONResponse)
async def delete(
    request_data: DeleteCabinetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 獲取 cabinet 信息（用於記錄 log）
        result = await db.execute(
            select(Cabinet).where(Cabinet.id == request_data.cabinet_id)
        )
        cabinet = result.scalar_one()
        home_id = cabinet.home_id
        
        # 刪除櫥櫃資料
        await _delete_db_cabinet(request_data, db)
        
        # 建立操作日誌
        log_result = await create_log(
            db=db,
            home_id=home_id,
            state=StateType.DELETE,
            item_type=ItemType.CABINET,
            user_name=request_data.user_name,
            operate_type=None,  # delete 操作不需要 operate_type
            log_type=LogType.NORMAL,
        )
        if not log_result:
            logger.warning("Failed to create cabinet log for cabinet_id=%s", str(request_data.cabinet_id))
        
        # 產生響應資料（不返回 data）
        return success_response()

    except SQLAlchemyError:
        if db.in_transaction():
            await db.rollback()
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_41)
    except Exception:
        if db.in_transaction():
            await db.rollback()
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_41)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: DeleteCabinetRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.cabinet_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_41)
    
    # 檢查 Cabinet 是否存在
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == request_data.cabinet_id)
    )
    cabinet = result.scalar_one_or_none()
    
    if not cabinet:
        return _error_handle(ServerErrorCode.CABINET_NOT_FOUND_41)
    
    return None

# 刪除櫥櫃資料
async def _delete_db_cabinet(
    request_data: DeleteCabinetRequest,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == request_data.cabinet_id)
    )
    cabinet = result.scalar_one()
    await db.delete(cabinet)
    await db.commit()

