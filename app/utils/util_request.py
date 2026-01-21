from typing import Optional
from uuid import UUID, uuid4
from fastapi import Request

_REQUEST_ID_KEY: str = "request_id"
_USER_ID_KEY: str = "current-member-id"

def get_user_id(request: Optional[Request] = None) -> Optional[int]:
    return _get_user_id_from_state(_USER_ID_KEY, request)

def _get_user_id_from_state(key: str, request: Optional[Request] = None) -> Optional[int]:
    if request is None:
        return None
    
    # 先尝试从 state 获取（可能是 UUID 或 int）
    cached_id = getattr(request.state, key, None)
    
    if cached_id is not None:
        # 如果已经缓存，转换为 int
        if isinstance(cached_id, int):
            return cached_id
        elif isinstance(cached_id, UUID):
            return cached_id.int
        else:
            return int(cached_id) if cached_id else None
    
    # 从 header 获取并转换
    result_id = _get_user_id_from_header(key, request)
    
    if result_id is not None:
        setattr(request.state, key, result_id)
    
    return result_id

def _get_user_id_from_header(key: str, request: Optional[Request] = None) -> Optional[int]:
    if request is None:
        return None
    
    result_id_str: Optional[str] = request.headers.get(key)
    
    if not result_id_str:
        return None
    
    try:
        # 先尝试解析为 UUID，然后转换为 int
        uuid_obj = UUID(result_id_str)
        return uuid_obj.int
    except (ValueError, TypeError):
        try:
            # 如果不是 UUID 格式，尝试直接转换为 int
            return int(result_id_str)
        except (ValueError, TypeError):
            return None
            
def get_request_id(request: Optional[Request] = None) -> Optional[UUID]:
    return _get_request_id_from_state(_REQUEST_ID_KEY, request)

def _get_request_id_from_state(key: str, request: Optional[Request] = None) -> Optional[UUID]:
    if request is None:
        return None
    
    cached_id = getattr(request.state, key, None)
    
    # 如果已经缓存且是 UUID 类型，直接返回
    if isinstance(cached_id, UUID):
        return cached_id
    
    # 如果缓存存在但不是 UUID 类型，或者缓存不存在，从 header 获取
    if cached_id is None:
        result_id = _get_request_id_from_header(key, request)
        return result_id
    
    # 如果缓存存在但不是 UUID 类型，返回 None（异常情况）
    return None

def _get_request_id_from_header(key: str, request: Optional[Request] = None) -> Optional[UUID]:
    if request is None:
        return None
    
    result_id_str: Optional[str] = request.headers.get(key)
    
    if not result_id_str:
        return None
    
    try:
        result_id = UUID(result_id_str)
        setattr(request.state, key, result_id)
        return result_id
    except (ValueError, TypeError):
        return None