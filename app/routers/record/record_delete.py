from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.record_service import delete_record
from app.schemas.record_request import RecordRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_log import log_info
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.delete("/", response_class=JSONResponse)
@router_exception_handler
async def delete(
    request: Request,
    request_model: RecordRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    await delete_record(request_model, db)
    response = success_response(data=None, request=request)
    bg_tasks.add_task(
        log_info,
        request_model.model_dump(),
        {},
        request
    )
    return response

def _error_check(
    request: Request,
    request_model: RecordRequestModel,
) -> None:
    # 檢查 user_id 是否存在
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
