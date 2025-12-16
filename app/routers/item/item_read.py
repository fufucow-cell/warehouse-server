from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.item_service import read_item
from app.schemas.item_request import ReadItemRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.get("/", response_class=JSONResponse)
@router_exception_handler
async def read(
    request: Request,
    item_id: Optional[UUID] = Query(None, description="Item ID"),
    cabinet_id: Optional[UUID] = Query(None, description="Cabinet ID"),
    household_id: Optional[UUID] = Query(None, description="Household ID"),
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, household_id)
    
    if not household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    request_model = ReadItemRequestModel(household_id=household_id)
    
    if cabinet_id is not None:
        request_model.cabinet_id = cabinet_id
    
    response_models = await read_item(request_model, db)
    
    # 如果指定了 item_id，从结果中筛选
    if item_id is not None:
        item = next((item for item in response_models if item.id == item_id), None)
        if not item:
            raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
        return success_response(data=item, request=request)
    
    return success_response(data=response_models, request=request)

def _error_check(
    request: Request,
    household_id: Optional[UUID],
) -> None:
    # 檢查 user_id 是否存在
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
