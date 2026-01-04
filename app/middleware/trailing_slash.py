from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable


class TrailingSlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # 获取原始路径
        path = request.url.path
        method = request.method
        
        # 只处理 POST, PUT, PATCH, DELETE 方法
        # 并且路径不以 / 结尾（排除根路径）
        if method in ["POST", "PUT", "PATCH", "DELETE"] and path and not path.endswith("/") and path != "/":
            # 检查是否是 API 路径
            if path.startswith("/api/v1/warehouse"):
                # 修改 scope 中的路径（在读取请求体之前修改，这样不会丢失请求体）
                new_path = path + "/"
                request.scope["path"] = new_path
                request.scope["raw_path"] = new_path.encode()
        
        # 继续处理请求
        response = await call_next(request)
        return response

