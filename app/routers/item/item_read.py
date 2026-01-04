from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.item.item_read_service import read_item
from app.schemas.item_request import ReadItemRequestModel
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
    bg_tasks: BackgroundTasks,
    request_model: ReadItemRequestModel = Depends(),
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    response_models = await read_item(request_model, db)
    response = success_response(data=response_models, request=request)
    bg_tasks.add_task(
        log_info,
        request_model.model_dump(),
        response_models if isinstance(response_models, list) else [response_models],
        request
    )
    return response

def _error_check(
    request: Request,
    request_model: ReadItemRequestModel,
) -> None:
    if not get_user_id(request):
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
    
    if not request_model.household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
