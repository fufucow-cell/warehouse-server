from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.cabinet_service import create_cabinet
from app.schemas.cabinet_request import CreateCabinetRequestModel
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
    request_model: CreateCabinetRequestModel,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    response_models = await create_cabinet(request_model, db)
    # create_cabinet 返回 List[CabinetResponseListModel]，需要找到刚创建的 cabinet
    # 由于创建后返回的是按 room_id 分组的列表，需要遍历找到包含新创建的 cabinet
    response_model = None
    for room_group in response_models:
        # 查找匹配 room_id 的组，然后取最后一个 cabinet（假设是刚创建的）
        if (request_model.room_id is None and room_group.room_id == "") or \
           (request_model.room_id is not None and room_group.room_id == str(request_model.room_id)):
            if room_group.cabinet:
                response_model = room_group.cabinet[-1]
                break
    
    if not response_model:
        raise ValidationError(ServerErrorCode.INTERNAL_SERVER_ERROR_42)
    
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
    request_model: CreateCabinetRequestModel,
) -> None:
    # 檢查 user_id 是否存在
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
