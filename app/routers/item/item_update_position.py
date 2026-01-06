from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.item.item_update_service import update_item_position
from app.schemas.item_request import UpdateItemPositionRequestModel
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
    request_model: UpdateItemPositionRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    await update_item_position(request_model, db)
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
    request_model: UpdateItemPositionRequestModel,
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
    
    # 檢查每個 cabinet 的 old_cabinet_id, new_cabinet_id 和 quantity
    for cabinet in request_model.cabinets:
        if cabinet.is_delete is False:
            # 檢查 old_cabinet_id 和 new_cabinet_id 不能相同（僅在非 is_delete 時）
            if cabinet.old_cabinet_id == cabinet.new_cabinet_id:
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
            
            # quantity 必須提供且大於等於 1
            if cabinet.quantity is None or cabinet.quantity < 1:
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)

