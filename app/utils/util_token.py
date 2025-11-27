"""
Token 验证工具函数
用于验证 access_token 并提取用户信息
"""
from typing import Optional
from jose import JWTError, jwt
from app.core.core_config import settings


def decode_token(token: str) -> Optional[dict]:
    """
    解码 Token（与 Auth Server 共享 JWT_SECRET_KEY）
    
    Args:
        token: Access Token
    
    Returns:
        dict: Token payload（如果解码成功）
        None: 如果解码失败
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[int]:
    """
    验证 Access Token 并提取 user_id
    
    Args:
        token: Access Token
    
    Returns:
        int: user_id（如果验证成功）
        None: 如果验证失败
    """
    payload = decode_token(token)
    
    if not payload:
        return None
    
    # 检查 Token 类型
    if payload.get("type") != "access":
        return None
    
    # 提取用户 ID
    user_id = payload.get("user_id")
    if not user_id:
        return None
    
    return user_id

