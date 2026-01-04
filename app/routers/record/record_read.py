from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.record_service import read_record
from app.schemas.record_request import RecordRequestModel
from app.schemas.record_response import RecordResponseModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_log import log_info
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.get("/", response_class=JSONResponse)
@router_exception_handler
async def read(
    request: Request,
    request_model: RecordRequestModel = Depends(),
    db: AsyncSession = Depends(get_db),
    bg_tasks: BackgroundTasks = BackgroundTasks()
):
    _error_check(request, request_model)
    response_models = await read_record(request_model, db)
    response = success_response(data=response_models, request=request)
    # 使用列表推导式将 response_models 转换为字典列表
    response_data = [model.model_dump() for model in response_models] if response_models else []
    bg_tasks.add_task(
        log_info,
        request_model.model_dump(),
        response_data,
        request
    )
    return response

def _error_check(
    request: Request,
    request_model: RecordRequestModel,
) -> None:
    if not get_user_id(request):
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)

    if not request_model.household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
