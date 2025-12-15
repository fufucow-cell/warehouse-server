from typing import Optional, Callable, Any
from functools import wraps
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.util_response import error_response
from app.utils.util_error_map import ServerErrorCode

class ValidationError(Exception):
    def __init__(self, code: int):
        self.code = code
        super().__init__(f"Validation error with code: {code}")

# 統一異常處理裝飾器
def router_exception_handler(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs):
        db: Optional[AsyncSession] = None
        request: Optional[Request] = None
        
        # 查找 db 参数
        if 'db' in kwargs:
            db = kwargs['db']
        else:
            for arg in args:
                if isinstance(arg, AsyncSession):
                    db = arg
                    break
        
        # 查找 request 参数
        if 'request' in kwargs:
            request = kwargs['request']
        else:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
        
        try:
            return await func(*args, **kwargs)
        except ValidationError as e:
            if db:
                await _rollback_if_needed(db)
            return error_response(e.code, request=request)
        except Exception as e:
            if db:
                await _rollback_if_needed(db)
            return error_response(internal_msg=str(e), request=request)
    
    return wrapper

async def _rollback_if_needed(db: AsyncSession) -> None:
    if db.in_transaction():
        await db.rollback()

# HTTP 异常处理器
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:    
    if exc.status_code == 404:
        # 请求路径不存在 → 使用 313 Request path invalid
        internal_code = ServerErrorCode.REQUEST_PATH_INVALID_31
    elif exc.status_code == 422:
        # FastAPI 参数验证错误 → 使用 312 Request parameters invalid
        internal_code = ServerErrorCode.REQUEST_PARAMETERS_INVALID_31
    else:
        # 其他 HTTP 错误 → 使用 310 Internal server error
        internal_code = ServerErrorCode.INTERNAL_SERVER_ERROR_31
    
    return error_response(
        internal_code=internal_code,
        internal_msg=str(exc),
        request=request
    )

# 请求验证异常处理器
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:    
    return error_response(
        internal_code=ServerErrorCode.REQUEST_PARAMETERS_INVALID_31,
        internal_msg=str(exc),
        request=request
    )

# 全局异常处理器
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        internal_code=ServerErrorCode.INTERNAL_SERVER_ERROR_31,
        internal_msg=str(exc),
        request=request
    )