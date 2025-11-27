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
from app.utils.util_validation import validate_user_can_modify_data

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
        
        # 刪除櫥櫃資料
        await _delete_db_cabinet(request_data, db)
        
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
    
    # 驗證用戶是否有權限刪除該櫥櫃（驗證用戶是否屬於該櫥櫃所屬的家庭）
    # 可以根據業務需求設置 require_role，例如只有 owner 或 admin 才能刪除
    is_valid, error_code = await validate_user_can_modify_data(
        user_id=user_id,
        data_home_id=cabinet.home_id,
        require_role=2  # 只有 owner(1) 或 admin(2) 才能刪除，member(3) 不能刪除
    )
    if not is_valid:
        return _error_handle(error_code)
    
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

