from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.item.item_update_service import update_item_normal
from app.schemas.item_request import UpdateItemNormalRequestModel
from app.schemas.item_response import ItemResponseModel
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
    request_model: UpdateItemNormalRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    response_model = await update_item_normal(request_model, db)
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
    request_model: UpdateItemNormalRequestModel,
) -> None:
    # 檢查 user_id 是否存在
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
    
    # 檢查 user_name 是否存在
    if not request_model.user_name or not request_model.user_name.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 檢查 name 不能為空字串（如果提供）
    if request_model.name is not None:
        if not request_model.name.strip():
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 檢查 min_stock_alert 不能為負數（如果提供）
    if request_model.min_stock_alert is not None:
        if request_model.min_stock_alert < 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)

