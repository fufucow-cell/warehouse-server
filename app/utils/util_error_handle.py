from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.utils.util_response import error_response
from app.utils.util_error_map import ServerErrorCode


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 异常处理器 - 转换为统一响应格式（HTTP 状态码始终为 200）"""
    # 根据 HTTP 状态码返回对应的内部错误码
    if exc.status_code == 404:
        internal_code = ServerErrorCode.REQUEST_PATH_INVALID_40
    elif exc.status_code == 422:
        internal_code = ServerErrorCode.REQUEST_PARAMETERS_INVALID_40
    else:
        internal_code = ServerErrorCode.INTERNAL_SERVER_ERROR_40
    
    error_resp = error_response(
        internal_code=internal_code
    )
    
    # 注意：所有日志已在 API Gateway 统一记录，此处不再记录
    
    return error_resp


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器 - 转换为统一响应格式（HTTP 状态码始终为 200）"""
    # 使用共用的 body 参数验证错误码
    error_resp = error_response(
        internal_code=ServerErrorCode.REQUEST_PARAMETERS_INVALID_40
    )
    
    # 注意：所有日志已在 API Gateway 统一记录，此处不再记录
    
    return error_resp


async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器 - 捕获所有未处理的异常"""
    # 创建错误响应（使用统一错误码 310）
    error_resp = error_response(
        internal_code=ServerErrorCode.INTERNAL_SERVER_ERROR_40
    )
    
    # 注意：所有日志已在 API Gateway 统一记录，此处不再记录
    
    return error_resp

