from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.cabinet_model import Cabinet
from app.schemas.warehouse_request import UpdateCabinetRequest
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header
from app.utils.util_validation import validate_user_can_modify_data, validate_home_and_room, validate_room_belongs_to_home

router = APIRouter()

# 路由入口
@router.put("/", response_class=JSONResponse)
async def update(
    request_data: UpdateCabinetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 修改櫥櫃資料
        await _update_db_cabinet(request_data, db)
        
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
    request_data: UpdateCabinetRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.cabinet_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)
    
    if request_data.name is not None and not request_data.name.strip():
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
    
    # 驗證用戶是否有權限修改該櫥櫃（驗證用戶是否屬於該櫥櫃所屬的家庭）
    is_valid, error_code = await validate_user_can_modify_data(
        user_id=user_id,
        data_home_id=cabinet.home_id
    )
    if not is_valid:
        return _error_handle(error_code)
    
    # 如果提供了 new_room_id，需要驗證 old_room_id 和 new_room_id 是否都屬於該家庭
    if request_data.new_room_id is not None:
        # 如果 cabinet 當前有 room_id，必須提供 old_room_id 來確認
        if cabinet.room_id is not None:
            if request_data.old_room_id is None:
                return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)
            
            # 驗證 old_room_id 是否與當前 cabinet 的 room_id 匹配
            if cabinet.room_id != request_data.old_room_id:
                return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)
        
        # 如果提供了 old_room_id，驗證它是否屬於該家庭
        if request_data.old_room_id is not None:
            is_valid, error_code = await validate_room_belongs_to_home(
                home_id=cabinet.home_id,
                room_id=request_data.old_room_id
            )
            if not is_valid:
                return _error_handle(error_code)
        
        # 驗證 new_room_id 是否屬於該家庭
        is_valid, error_code = await validate_room_belongs_to_home(
            home_id=cabinet.home_id,
            room_id=request_data.new_room_id
        )
        if not is_valid:
            return _error_handle(error_code)
    
    # 如果修改了 home_id，需要驗證新的 home_id 是否有效
    if request_data.home_id is not None:
        new_home_id = request_data.home_id
        is_valid, error_code, _ = await validate_home_and_room(
            user_id=user_id,
            home_id=new_home_id,
            room_id=None  # 不驗證 room_id，因為可能只是修改 home_id
        )
        if not is_valid:
            return _error_handle(error_code)
    
    return None

# 修改櫥櫃資料
async def _update_db_cabinet(
    request_data: UpdateCabinetRequest,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == request_data.cabinet_id)
    )
    cabinet = result.scalar_one()
    
    # 更新 new_room_id（如果提供）
    if request_data.new_room_id is not None:
        cabinet.room_id = request_data.new_room_id
    if request_data.home_id is not None:
        cabinet.home_id = request_data.home_id
    if request_data.name is not None:
        cabinet.name = request_data.name
    if request_data.description is not None:
        cabinet.description = request_data.description
    
    await db.commit()

