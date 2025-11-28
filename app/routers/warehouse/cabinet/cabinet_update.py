from typing import Optional, List
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
from app.utils.util_log import create_log
from app.models.log_model import StateType, ItemType, OperateType, LogType
import logging

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
        
        # 獲取舊的 cabinet 信息（用於檢測字段變化）
        old_result = await db.execute(
            select(Cabinet).where(Cabinet.id == request_data.cabinet_id)
        )
        old_cabinet = old_result.scalar_one()
        
        # 立即保存舊值（避免 SQLAlchemy 對象被修改後影響比較）
        old_values = {
            'name': old_cabinet.name,
            'description': old_cabinet.description,
            'room_id': old_cabinet.room_id,
            'home_id': old_cabinet.home_id
        }
        
        # 修改櫥櫃資料（返回更新後的 cabinet 以便記錄 log）
        updated_cabinet = await _update_db_cabinet(request_data, db)
        
        # 建立操作日誌
        operate_types = _detect_operate_types(request_data, old_values, updated_cabinet)
        log_result = await create_log(
            db=db,
            home_id=updated_cabinet.home_id,
            state=StateType.MODIFY,
            item_type=ItemType.CABINET,
            user_name=request_data.user_name,
            operate_type=operate_types if operate_types else None,
            log_type=LogType.NORMAL,
        )
        if not log_result:
            logging.getLogger(__name__).warning("Failed to create cabinet log for cabinet_id=%s", str(updated_cabinet.id))
        
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
    
    return None

# 修改櫥櫃資料
async def _update_db_cabinet(
    request_data: UpdateCabinetRequest,
    db: AsyncSession
) -> Cabinet:
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
    await db.refresh(cabinet)
    return cabinet


# 檢測操作類型
def _detect_operate_types(
    request_data: UpdateCabinetRequest,
    old_values: dict,
    updated_cabinet: Cabinet
) -> List[OperateType]:
    """檢測哪些字段被修改了，返回對應的 OperateType 列表"""
    operate_types: List[OperateType] = []
    
    # 檢查 name 是否被修改（使用保存的舊值進行比較）
    if request_data.name is not None:
        old_name = old_values['name'] if old_values['name'] is not None else ""
        new_name = request_data.name if request_data.name is not None else ""
        if old_name != new_name:
            operate_types.append(OperateType.NAME)
    
    # 檢查 description 是否被修改（使用保存的舊值進行比較）
    if request_data.description is not None:
        # 處理 None 的情況：將 None 視為空字符串進行比較
        old_desc = old_values['description'] if old_values['description'] is not None else ""
        new_desc = request_data.description if request_data.description is not None else ""
        if old_desc != new_desc:
            operate_types.append(OperateType.DESCRIPTION)
    
    # 檢查是否移動（room_id 或 home_id 變化）
    room_id_changed = False
    home_id_changed = False
    
    if request_data.new_room_id is not None:
        # 使用保存的舊值進行比較
        old_room_id = old_values['room_id']
        new_room_id = request_data.new_room_id
        if old_room_id != new_room_id:
            room_id_changed = True
    
    if request_data.home_id is not None:
        # 使用保存的舊值進行比較
        old_home_id = old_values['home_id']
        new_home_id = request_data.home_id
        if old_home_id != new_home_id:
            home_id_changed = True
    
    if room_id_changed or home_id_changed:
        operate_types.append(OperateType.MOVE)
    
    return operate_types

