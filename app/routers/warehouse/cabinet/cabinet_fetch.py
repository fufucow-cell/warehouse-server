from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.table.cabinet_model import Cabinet
from app.schemas.cabinet_response import CabinetResponseModel
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 路由入口
@router.get("/", response_class=JSONResponse)
async def fetch(
    request: Request,
    cabinet_id: Optional[UUID] = Query(None, description="Cabinet ID"),
    room_id: Optional[UUID] = Query(None, description="Room ID"),
    household_id: Optional[UUID] = Query(None, description="Household ID"),
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
        user_id = get_user_id_from_header(request)
        if not user_id:
            return _error_handle(ServerErrorCode.UNAUTHORIZED_40)

        # 如果帶入 cabinet_id，返回單筆櫥櫃詳細資料
        if cabinet_id is not None:
            cabinet = await _get_db_cabinet(cabinet_id, db)
            if not cabinet:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_40)
            
            response_data = CabinetResponseModel.model_validate(cabinet).model_dump(
                mode="json",
                exclude_none=True,
            )
            return success_response(data=response_data)
        
        # 如果同時帶入 household_id 和 room_id，返回該家庭該房間的所有櫥櫃
        if household_id is not None and room_id is not None:
            cabinets = await _get_db_cabinets_by_home_and_room(household_id, room_id, db)
            cabinets_data = [
                CabinetResponseModel.model_validate(cabinet).model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for cabinet in cabinets
            ]
            return success_response(data=cabinets_data)
        
        # 如果只帶入 room_id，返回該房間的所有櫥櫃
        if room_id is not None:
            cabinets = await _get_db_cabinets_by_room(room_id, db)
            cabinets_data = [
                CabinetResponseModel.model_validate(cabinet).model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for cabinet in cabinets
            ]
            return success_response(data=cabinets_data)
        
        # 如果只帶入 household_id，返回該家庭的所有櫥櫃
        if household_id is not None:
            cabinets = await _get_db_cabinets_by_home(household_id, db)
            cabinets_data = [
                CabinetResponseModel.model_validate(cabinet).model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for cabinet in cabinets
            ]
            return success_response(data=cabinets_data)
        
        # 如果都沒有，返回錯誤
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_40)

    except SQLAlchemyError:
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception:
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 獲取單筆櫥櫃
async def _get_db_cabinet(
    cabinet_id: UUID,
    db: AsyncSession
) -> Optional[Cabinet]:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == cabinet_id)
    )
    return result.scalar_one_or_none()

# 獲取房間的所有櫥櫃
async def _get_db_cabinets_by_room(
    room_id: UUID,
    db: AsyncSession
) -> list[Cabinet]:
    result = await db.execute(
        select(Cabinet).where(Cabinet.room_id == room_id)
    )
    return list(result.scalars().all())

# 獲取家庭的所有櫥櫃
async def _get_db_cabinets_by_home(
    household_id: UUID,
    db: AsyncSession
) -> list[Cabinet]:
    result = await db.execute(
        select(Cabinet).where(Cabinet.household_id == household_id)
    )
    return list(result.scalars().all())

# 獲取家庭和房間的所有櫥櫃
async def _get_db_cabinets_by_home_and_room(
    household_id: UUID,
    room_id: UUID,
    db: AsyncSession
) -> list[Cabinet]:
    result = await db.execute(
        select(Cabinet).where(
            Cabinet.household_id == household_id,
            Cabinet.room_id == room_id
        )
    )
    return list(result.scalars().all())

