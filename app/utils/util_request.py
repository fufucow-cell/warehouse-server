from typing import Optional
from uuid import uuid4, UUID
from contextvars import ContextVar
from fastapi import Request

# 使用 contextvars 來暫存每個請求的 request_id（支持並發）
_request_id_context: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id(request: Optional[Request] = None) -> str:
    if request is not None:
        # 1. 優先使用 request.state.request_id
        if hasattr(request.state, "request_id") and request.state.request_id:
            request_id = request.state.request_id
        else:
            # 2. 再取 header: request_id
            header_value = (request.headers.get("request_id") or "").strip()
            if header_value:
                request_id = header_value
            else:
                # 3. 若都沒有則自己生成新的 UUID
                request_id = str(uuid4())
            
            # 將 request_id 寫回 request.state，供後續流程使用
            request.state.request_id = request_id
        
        # 無論從哪裡獲取到 request_id，都要設置到 context 中
        _request_id_context.set(request_id)
        return request_id
    else:
        # 從 context 獲取
        request_id = _request_id_context.get("")
        if not request_id:
            # 如果 context 中沒有，生成一個新的（不應該發生，但為了安全）
            request_id = str(uuid4())
            _request_id_context.set(request_id)
        return request_id


def get_user_id_from_header(request: Request) -> Optional[UUID]:
    # Starlette Headers 是大小写不敏感的，但内部存储为小写
    user_id_str = request.headers.get("X-User-ID", "").strip()
    if not user_id_str:
        return None
    
    # 去除可能的引号（Postman 或其他客户端可能会在 header 值中添加引号）
    user_id_str = user_id_str.strip('"').strip("'")
    
    try:
        return UUID(user_id_str)
    except (ValueError, TypeError):
        return None