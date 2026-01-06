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
    await update_cabinet(request_model, db)
    response = success_response(data=None, request=request)
    bg_tasks.add_task(
        log_info,
        request_model.model_dump(),
        None,
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
    
    # 檢查 user_name 是否存在
    if not request_model.user_name or not request_model.user_name.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 檢查 cabinets 列表不為空
    if not request_model.cabinets or len(request_model.cabinets) == 0:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 檢查每個 cabinet 的 cabinet_id 和更新字段
    for cabinet in request_model.cabinets:
        # cabinet_id 必須提供
        if cabinet.cabinet_id is None:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        
        # 如果提供了 new_cabinet_name，不能為空字串
        if cabinet.new_cabinet_name is not None:
            if not cabinet.new_cabinet_name.strip():
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)