from typing import Optional, Union
from uuid import UUID


def uuid_to_str(uuid_value: Optional[Union[str, UUID]]) -> Optional[str]:
    if uuid_value is None:
        return None
    if isinstance(uuid_value, str):
        return uuid_value
    if isinstance(uuid_value, UUID):
        return str(uuid_value)

def str_to_uuid(uuid_str: Optional[Union[str, UUID]]) -> Optional[UUID]:
    if uuid_str is None:
        return None
    if isinstance(uuid_str, UUID):
        return uuid_str
    if isinstance(uuid_str, str):
        try:
            return UUID(uuid_str)
        except (ValueError, AttributeError):
            return None

