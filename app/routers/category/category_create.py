from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.category.category_create_service import create_category
from app.schemas.category_request import CreateCategoryRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_log import log_info
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.post("/", response_class=JSONResponse)
@router_exception_handler
async def create(
    request: Request,
    request_model: CreateCategoryRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    response_model = await create_category(request_model, db)
    
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
    request_model: CreateCategoryRequestModel,
) -> None:
    if not get_user_id(request):
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)

    if not request_model.user_name:
        raise ValidationError(ServerErrorCode.PARAMETERS_INVALID_42)