from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.cabinet_service import read_cabinet
from app.schemas.cabinet_request import ReadCabinetRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.get("/", response_class=JSONResponse)
@router_exception_handler
async def read(
    request: Request,
    cabinet_id: Optional[UUID] = Query(None, description="Cabinet ID"),
    room_id: Optional[UUID] = Query(None, description="Room ID"),
    household_id: Optional[UUID] = Query(None, description="Household ID"),
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, household_id)
    
    if not household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    request_model = ReadCabinetRequestModel(household_id=household_id)
    
    if cabinet_id is not None:
        request_model.cabinet_ids = [cabinet_id]
    elif room_id is not None:
        request_model.room_id = room_id
    
    response_models = await read_cabinet(request_model, db)
    
    # 如果指定了 cabinet_id，返回單一 cabinet；否則返回列表
    if cabinet_id is not None:
        cabinet = next((cab for cab in response_models if cab.cabinet_id == cabinet_id), None)
        if not cabinet:
            raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
        return success_response(data=cabinet, request=request)
    
    return success_response(data=response_models, request=request)

def _error_check(
    request: Request,
    household_id: Optional[UUID],
) -> None:
    # 檢查 user_id 是否存在
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
