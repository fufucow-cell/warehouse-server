"""
验证工具函数
用于验证 home_id 和 room_id 是否有效且属于用户
"""
import httpx  # type: ignore[import-untyped]
from typing import Optional, Tuple
from uuid import UUID
from app.core.core_config import settings
from app.utils.util_error_map import ServerErrorCode
import logging

logger = logging.getLogger(__name__)


async def validate_home_access(
    user_id: UUID,
    home_id: int
) -> Tuple[bool, Optional[int], Optional[int]]:
    """
    验证用户是否有权限访问指定的 home_id，并返回用户的 role
    
    Args:
        user_id: 用户 ID
        home_id: 家庭 ID
        
    Returns:
        Tuple[bool, Optional[int], Optional[int]]: (是否有效, 错误码, 用户角色)
        - 如果有效: (True, None, role)
        - 如果无效: (False, error_code, None)
        - role: 1=owner, 2=admin, 3=member (根据 household_server 的定义)
    """
    try:
        # 调用 Household Server 的 API 获取用户所属的家庭列表
        # 注意：URL 末尾需要加斜杠，避免 307 重定向
        url = f"{settings.HOUSEHOLD_SERVER_URL}/api/v1/household/home/"
        headers = {
            "X-User-ID": str(user_id),
            "Content-Type": "application/json"
        }
        
        # 设置 follow_redirects=True 自动跟随重定向
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            
            # 记录响应状态码和内容，便于调试
            logger.debug(f"Household Server response status: {response.status_code}")
            logger.debug(f"Household Server response headers: {dict(response.headers)}")
            
            if response.status_code == 401:
                # 未授权
                logger.warning(f"Household Server returned 401 Unauthorized for user_id: {user_id}")
                return False, ServerErrorCode.UNAUTHORIZED_41, None
            
            if response.status_code != 200:
                response_text = response.text[:500]  # 只记录前500个字符
                logger.error(f"Household Server returned status {response.status_code}, response: {response_text}")
                logger.error(f"Request URL: {url}, Headers: {headers}")
                return False, ServerErrorCode.CABINET_SERVICE_FAILED_41, None
            
            try:
                response_data = response.json()
            except Exception as e:
                logger.error(f"Failed to parse Household Server response as JSON: {e}, response text: {response.text[:500]}")
                return False, ServerErrorCode.CABINET_SERVICE_FAILED_41, None
            
            logger.debug(f"Household Server response data: {response_data}")
            
            # 解析响应数据
            # Household Server 返回格式：{"internal_code": 200, "internal_message": "Success", "external_code": 200, "external_message": "Success", "request_id": "...", "data": [{"home_id": 1, "home_name": "...", "role": 1}, ...]}
            if isinstance(response_data, dict):
                # 检查响应是否成功（internal_code 应该是 200）
                internal_code = response_data.get("internal_code")
                if internal_code != 200:
                    logger.error(f"Household Server returned error, internal_code: {internal_code}, message: {response_data.get('internal_message', 'Unknown error')}")
                    return False, ServerErrorCode.CABINET_SERVICE_FAILED_41, None
                
                # 检查是否有 data 字段
                if "data" in response_data:
                    homes = response_data["data"]
                    # 检查 home_id 是否在用户所属的家庭列表中
                    for home in homes:
                        if home.get("home_id") == home_id:
                            role = home.get("role")
                            logger.debug(f"Found home_id {home_id} with role {role}")
                            return True, None, role
                else:
                    logger.warning(f"Household Server response missing 'data' field: {response_data}")
            
            # home_id 不在用户所属的家庭列表中
            logger.warning(f"Home_id {home_id} not found in user's home list")
            # 使用错误码 416 (Home not found)
            return False, 416, None
            
    except httpx.ConnectError:
        logger.error("Failed to connect to Household Server")
        return False, ServerErrorCode.CABINET_SERVICE_FAILED_41
    except httpx.TimeoutException:
        logger.error("Timeout when connecting to Household Server")
        return False, ServerErrorCode.CABINET_SERVICE_FAILED_41
    except Exception as e:
        logger.error(f"Error validating home access: {e}", exc_info=True)
        return False, ServerErrorCode.INTERNAL_SERVER_ERROR_41


async def validate_room_belongs_to_home(
    home_id: int,
    room_id: int
) -> Tuple[bool, Optional[int]]:
    """
    验证 room_id 是否属于指定的 home_id
    
    Args:
        home_id: 家庭 ID
        room_id: 房间 ID
        
    Returns:
        Tuple[bool, Optional[int]]: (是否有效, 错误码)
        - 如果有效: (True, None)
        - 如果无效: (False, error_code)
    """
    try:
        # 调用 Household Server 的 API 获取指定 home_id 下的所有房间
        # 注意：URL 末尾需要加斜杠，避免 307 重定向
        url = f"{settings.HOUSEHOLD_SERVER_URL}/api/v1/household/room/"
        params = {"home_id": home_id}
        
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            
            logger.debug(f"Household Server room response status: {response.status_code}")
            
            if response.status_code != 200:
                response_text = response.text[:500]
                logger.error(f"Household Server returned status {response.status_code}, response: {response_text}")
                return False, ServerErrorCode.CABINET_SERVICE_FAILED_41
            
            try:
                response_data = response.json()
            except Exception as e:
                logger.error(f"Failed to parse Household Server response as JSON: {e}, response text: {response.text[:500]}")
                return False, ServerErrorCode.CABINET_SERVICE_FAILED_41
            
            logger.debug(f"Household Server room response data: {response_data}")
            
            # 解析响应数据
            # Household Server 返回格式：{"internal_code": 200, "internal_message": "Success", "external_code": 200, "external_message": "Success", "request_id": "...", "data": [{"room_id": 1, "room_name": "..."}, ...]}
            if isinstance(response_data, dict):
                # 检查响应是否成功（internal_code 应该是 200）
                internal_code = response_data.get("internal_code")
                if internal_code != 200:
                    logger.error(f"Household Server returned error, internal_code: {internal_code}, message: {response_data.get('internal_message', 'Unknown error')}")
                    return False, ServerErrorCode.CABINET_SERVICE_FAILED_41
                
                # 检查是否有 data 字段
                if "data" in response_data:
                    rooms = response_data["data"]
                    # 检查 room_id 是否在该 home 的房间列表中
                    for room in rooms:
                        if room.get("room_id") == room_id:
                            logger.debug(f"Found room_id {room_id} in home_id {home_id}")
                            return True, None
                else:
                    logger.warning(f"Household Server response missing 'data' field: {response_data}")
            
            # room_id 不属于该 home_id
            logger.warning(f"Room_id {room_id} not found in home_id {home_id}")
            # 使用错误码 417 (Room not found)
            return False, 417
            
    except httpx.ConnectError:
        logger.error("Failed to connect to Household Server")
        return False, ServerErrorCode.CABINET_SERVICE_FAILED_41
    except httpx.TimeoutException:
        logger.error("Timeout when connecting to Household Server")
        return False, ServerErrorCode.CABINET_SERVICE_FAILED_41
    except Exception as e:
        logger.error(f"Error validating room belongs to home: {e}", exc_info=True)
        return False, ServerErrorCode.INTERNAL_SERVER_ERROR_41


async def validate_home_and_room(
    user_id: UUID,
    home_id: int,
    room_id: Optional[int] = None
) -> Tuple[bool, Optional[int], Optional[int]]:
    """
    验证 home_id 和 room_id（如果提供）是否有效且属于用户，并返回用户的 role
    
    Args:
        user_id: 用户 ID
        home_id: 家庭 ID（必填）
        room_id: 房间 ID（可选）
        
    Returns:
        Tuple[bool, Optional[int], Optional[int]]: (是否有效, 错误码, 用户角色)
        - 如果有效: (True, None, role)
        - 如果无效: (False, error_code, None)
        - role: 1=owner, 2=admin, 3=member (根据 household_server 的定义)
    """
    # 首先验证 home_id 是否属于用户
    is_valid, error_code, role = await validate_home_access(user_id, home_id)
    if not is_valid:
        return False, error_code, None
    
    # 如果提供了 room_id，验证它是否属于该 home_id
    if room_id is not None:
        is_valid, error_code = await validate_room_belongs_to_home(home_id, room_id)
        if not is_valid:
            return False, error_code, None
    
    return True, None, role


async def validate_user_can_modify_data(
    user_id: UUID,
    data_home_id: int,
    require_role: Optional[int] = None
) -> Tuple[bool, Optional[int]]:
    """
    验证用户是否有权限修改/删除数据
    
    Args:
        user_id: 用户 ID
        data_home_id: 数据所属的家庭 ID
        require_role: 需要的最低角色权限（1=owner, 2=admin, 3=member）
                    如果为 None，则只需要是家庭成员即可
        
    Returns:
        Tuple[bool, Optional[int]]: (是否有效, 错误码)
        - 如果有效: (True, None)
        - 如果无效: (False, error_code)
    """
    # 验证用户是否有权限访问该 home_id，并获取用户的 role
    is_valid, error_code, role = await validate_home_access(user_id, data_home_id)
    if not is_valid:
        return False, error_code
    
    # 如果指定了需要的最低角色权限，检查用户的 role 是否足够
    if require_role is not None and role is not None:
        if role > require_role:  # role 数字越小，权限越高（1=owner, 2=admin, 3=member）
            return False, ServerErrorCode.UNAUTHORIZED_41
    
    return True, None

