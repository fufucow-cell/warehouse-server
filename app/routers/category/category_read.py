from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.services.category.category_read_service import read_category
from app.schemas.category_request import ReadCategoryRequestModel
from app.utils.util_response import success_response
from app.utils.util_request import get_user_id
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError, router_exception_handler

router = APIRouter()

@router.get("/", response_class=JSONResponse)
@router_exception_handler
async def read(
    request: Request,
    request_model: ReadCategoryRequestModel = Depends(),
    db: AsyncSession = Depends(get_db)
):
    _error_check(request, request_model)
    response_models = await read_category(request_model, db)
    return success_response(data=response_models, request=request)

def _error_check(
    request: Request,
    request_model: ReadCategoryRequestModel,
) -> None:
    user_id = get_user_id(request)
    if not user_id:
        raise ValidationError(ServerErrorCode.UNAUTHORIZED_42)
    
    if not request_model.household_id:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
