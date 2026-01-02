from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.cabinet.cabinet_update_service import update_cabinet
from app.schemas.cabinet_request import UpdateCabinetRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_log import log_info
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.put("/", response_class=JSONResponse)
@router_exception_handler
async def update(
    request: Request,
    request_model: UpdateCabinetRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    response_models = await update_cabinet(request_model, db)
    response_model = None
    for room_group in response_models:
        cabinet = next((cab for cab in room_group.cabinet if cab.cabinet_id == request_model.cabinet_id), None)
        if cabinet:
            response_model = cabinet
            break
    
    if not response_model:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    response = success_response(data=response_model, request=request)
    bg_tasks.add_task(
        log_info,
        request_model.model_dump(),
        response_model.model_dump(),
        request
    )
    return response

def _error_check(
    request: Request,
    request_model: UpdateCabinetRequestModel,
) -> None:
    # 檢查 user_id 是否存在
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
