from typing import Optional, Any, Union
from uuid import UUID
from fastapi import status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.utils.util_error_map import ERROR_CODE_TO_MESSAGE, ServerErrorCode
from app.utils.util_request import get_request_id
from app.utils.util_log import log_response

class BaseResponse(BaseModel):
    internal_code: int
    internal_message: str
    external_code: int
    external_message: str
    request_id: Optional[UUID] = None
    data: Optional[Any] = None
    
    def toJSON(self) -> JSONResponse:
        content = self.model_dump(exclude_none=True, mode='json')
        return JSONResponse(
            content=content,
            status_code=status.HTTP_200_OK
        )


# 成功響應
def success_response(
    data: Optional[Any] = None,
    request: Optional[Request] = None
) -> JSONResponse:
    response = BaseResponse(
        internal_code=status.HTTP_200_OK,
        internal_message="Success",
        external_code=status.HTTP_200_OK,
        external_message="Success",
        request_id=get_request_id(request),
        data=data
    )
    log_response(response.model_dump(), request)
    return response.toJSON()

# 錯誤響應
def error_response(
    internal_code: int = ServerErrorCode.INTERNAL_SERVER_ERROR_31,
    internal_msg: Optional[str] = None,
    request: Optional[Request] = None
) -> JSONResponse:
    default_code = ServerErrorCode.INTERNAL_SERVER_ERROR_31
    default_message = ERROR_CODE_TO_MESSAGE[default_code]
    external_message = ERROR_CODE_TO_MESSAGE.get(internal_code, default_message)
    internal_message = internal_msg or external_message
    response = BaseResponse(
        internal_code=internal_code,
        internal_message=internal_message,
        external_code=internal_code,
        external_message=external_message,
        request_id=get_request_id(request),
        data=None
    )
    log_response(response.model_dump(), request)
    return response.toJSON()


