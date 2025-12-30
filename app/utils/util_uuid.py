"""
UUID 工具函数
用于处理 UUID 对象和字符串之间的转换（MySQL 使用字符串存储 UUID）
"""
from typing import Optional, Union
from uuid import UUID


def uuid_to_str(uuid_value: Optional[Union[str, UUID]]) -> Optional[str]:
    """
    将 UUID 对象或字符串转换为字符串
    
    Args:
        uuid_value: UUID 对象或字符串
        
    Returns:
        字符串形式的 UUID，如果输入为 None 则返回 None
    """
    if uuid_value is None:
        return None
    if isinstance(uuid_value, str):
        return uuid_value
    if isinstance(uuid_value, UUID):
        return str(uuid_value)
    return str(uuid_value)


def str_to_uuid(uuid_str: Optional[Union[str, UUID]]) -> Optional[UUID]:
    """
    将字符串转换为 UUID 对象
    
    Args:
        uuid_str: UUID 字符串或 UUID 对象
        
    Returns:
        UUID 对象，如果输入为 None 或无效则返回 None
    """
    if uuid_str is None:
        return None
    if isinstance(uuid_str, UUID):
        return uuid_str
    if isinstance(uuid_str, str):
        try:
            return UUID(uuid_str)
        except (ValueError, AttributeError):
            return None
    return None

