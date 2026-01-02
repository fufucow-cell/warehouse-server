from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.category.category_update_service import update_category
from app.schemas.category_request import UpdateCategoryRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_log import log_info
from app.utils.util_error_handle import ValidationError, router_exception_handler
from app.utils.util_uuid import str_to_uuid

router = APIRouter()

@router.put("/", response_class=JSONResponse)
@router_exception_handler
async def update(
    request: Request,
    request_model: UpdateCategoryRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    await update_category(request_model, db)
    # 重新讀取更新後的分類用於響應
    from app.services.category.category_read_service import read_category
    from app.schemas.category_request import ReadCategoryRequestModel
    response_models = await read_category(
        ReadCategoryRequestModel(household_id=request_model.household_id, category_id=request_model.category_id),
        db
    )
    response_model = response_models[0] if response_models else None
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
    request_model: UpdateCategoryRequestModel,
) -> None:
    # 檢查 user_id 是否存在
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
    
    # 檢查 user_name 是否存在
    if not request_model.user_name:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 檢查 name 不能為空字串
    if request_model.name is not None:
        if not request_model.name.strip():
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 防止 parent_id 設置為自己的 category_id（避免死循環）
    if request_model.parent_id and request_model.parent_id != "":
        parent_id_uuid = str_to_uuid(request_model.parent_id)
        if parent_id_uuid and parent_id_uuid == request_model.category_id:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
