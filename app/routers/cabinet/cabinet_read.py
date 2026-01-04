from typing import List
from typing import Optional
from uuid import UUID
from app.schemas.cabinet_response import CabinetInRoomResponseModel
from app.services.cabinet.cabinet_read_service import read_cabinet_by_room
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.schemas.cabinet_request import ReadCabinetByRoomRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.get("/", response_class=JSONResponse)
@router_exception_handler
async def read(
    request: Request,
    request_model: ReadCabinetByRoomRequestModel = Depends(),
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    response_models: List[CabinetInRoomResponseModel] = await read_cabinet_by_room(request_model, db, include_items=False)
    return success_response(data=response_models, request=request)

def _error_check(
    request: Request,
    request_model: ReadCabinetByRoomRequestModel,
) -> None:
    if not get_user_id(request):
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
    
    if not request_model.household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
