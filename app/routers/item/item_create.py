from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.item.item_create_service import create_item
from app.schemas.item_request import CreateItemRequestModel
from app.schemas.item_response import ItemResponseModel
from app.table import Cabinet
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_log import log_info
from app.utils.util_error_handle import ValidationError, router_exception_handler
from app.utils.util_uuid import uuid_to_str

router = APIRouter()

@router.post("/", response_class=JSONResponse)
@router_exception_handler
async def create(
    request: Request,
    request_model: CreateItemRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    await _error_check(request, request_model, db)
    response_model = await create_item(request_model, db)
    response = success_response(data=response_model, request=request)
    bg_tasks.add_task(
        log_info,
        request_model.model_dump(),
        response_model.model_dump(),
        request
    )
    return response

async def _error_check(
    request: Request,
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> None:
    if not get_user_id(request):
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
    
    if not request_model.household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if not request_model.user_name or not request_model.user_name.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if not request_model.name or not request_model.name.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if request_model.quantity < 0:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if request_model.min_stock_alert < 0:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 驗證 cabinet_id 是否在 cabinet 表中存在（如果提供了 cabinet_id）
    if request_model.cabinet_id is not None:
        cabinet_query = select(Cabinet).where(
            Cabinet.id == uuid_to_str(request_model.cabinet_id),
            Cabinet.household_id == uuid_to_str(request_model.household_id)
        )
        cabinet_result = await db.execute(cabinet_query)
        cabinet = cabinet_result.scalar_one_or_none()
        if not cabinet:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)

