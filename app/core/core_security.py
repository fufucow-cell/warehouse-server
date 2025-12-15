from typing import Optional
from jose import JWTError, ExpiredSignatureError, jwt
from app.core.core_config import settings

# 解码 JWT token（验证从 auth_server 来的 token）
def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except (ExpiredSignatureError, JWTError):
        return None

# 验证访问令牌并返回 user_id
def verify_access_token(token: str) -> Optional[int]:
    payload = decode_token(token)
    
    if not payload:
        return None
    
    if payload.get("type") != "access":
        return None
    
    user_id = payload.get("user_id")
    if not user_id:
        return None
    
    return user_id