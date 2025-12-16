from typing import Optional
from uuid import UUID, uuid4
from fastapi import Request

_REQUEST_ID_KEY: str = "request_id"
_USER_ID_KEY: str = "user_id"

def get_request_id(request: Optional[Request] = None) -> Optional[UUID]:
    return _get_id(_REQUEST_ID_KEY, request)

def get_user_id(request: Optional[Request] = None) -> Optional[UUID]:
    return _get_id(_USER_ID_KEY, request)

def get_user_id_from_header(request: Optional[Request] = None) -> Optional[UUID]:
    return get_user_id(request)

def _get_id(key: str, request: Optional[Request] = None) -> Optional[UUID]:
    if request is None:
        return None
    
    result_id: Optional[UUID] = getattr(request.state, key, None)
    
    if result_id is None:
        result_id = _handle_id(key, request)
    
    return result_id

def _handle_id(key: str, request: Optional[Request] = None) -> Optional[UUID]:
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