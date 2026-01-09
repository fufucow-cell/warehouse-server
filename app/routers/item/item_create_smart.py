from app.db.session import get_db
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from app.services.item.item_create_service import recognize_item_from_image, recognize_item_from_image_test
from app.schemas.item_request import CreateItemSmartRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id, get_request_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_log import log_info
from app.utils.util_error_handle import ValidationError, router_exception_handler
from app.utils.util_file import validate_base64_image
from app.core.core_config import settings
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/", response_class=JSONResponse)
@router_exception_handler
async def recognize(
    request: Request,
    request_model: CreateItemSmartRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    await _error_check(request, request_model)
    
    # 獲取 user_id 和 request_id 用於日誌記錄
    user_id = str(get_user_id(request)) if get_user_id(request) else None
    request_id = str(get_request_id(request)) if get_request_id(request) else None
    
    response_model = await recognize_item_from_image(request_model, db, user_id, request_id, request_model.user_name)
    response = success_response(data=response_model, request=request)
    bg_tasks.add_task(
        log_info,
        {"household_id": str(request_model.household_id), "image_length": len(request_model.image)},
        response_model.model_dump(),
        request
    )
    return response

async def _error_check(
    request: Request,
    request_model: CreateItemSmartRequestModel
) -> None:
    if not get_user_id(request):
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
    
    if not request_model.household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if not request_model.image or not request_model.image.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if not request_model.language or not request_model.language.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if not request_model.user_name or not request_model.user_name.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 檢查 API key 是否配置
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key":
        raise ValidationError(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    
    # 驗證 base64 圖片
    if not validate_base64_image(request_model.image):
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)

