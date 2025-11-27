from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.cabinet_model import Cabinet
from app.schemas.warehouse_request import CreateCabinetRequest
from app.schemas.warehouse_response import CabinetResponse
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header
from app.utils.util_validation import validate_home_and_room

router = APIRouter()

# 路由入口
@router.post("/", response_class=JSONResponse)
async def create(
    request_data: CreateCabinetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 創建櫥櫃資料
        new_cabinet = await _create_db_cabinet(request_data, db)
        
        # 產生響應資料
        response_data = CabinetResponse.model_validate(new_cabinet).model_dump(
            mode="json",
            exclude_none=True,
        )
        return success_response(data=response_data)

    except SQLAlchemyError as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SQLAlchemyError in create cabinet: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_41)
    except Exception as e:
        if db.in_transaction():
            await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exception in create cabinet: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_41)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: CreateCabinetRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.name or not request_data.name.strip():
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_41)
    
    # 驗證 home_id 和 room_id（如果提供）是否有效且屬於用戶
    is_valid, error_code, _ = await validate_home_and_room(
        user_id=user_id,
        home_id=request_data.home_id,
        room_id=request_data.room_id
    )
    if not is_valid:
        return _error_handle(error_code)

    return None

# 創建櫥櫃資料
async def _create_db_cabinet(
    request_data: CreateCabinetRequest,
    db: AsyncSession
) -> Cabinet:
    """創建櫥櫃資料"""
    new_cabinet = Cabinet(
        home_id=request_data.home_id,
        room_id=request_data.room_id,  # room_id 可能为 None
        name=request_data.name,
        description=request_data.description
    )
    db.add(new_cabinet)
    await db.commit()
    await db.refresh(new_cabinet)
    return new_cabinet

