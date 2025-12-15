"""
内部 API：从 Household Server 获取房间信息
用于 warehouse server 内部调用，不需要认证
"""
import httpx  # type: ignore[import-untyped]
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.core_config import settings
from app.db.session import get_db
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id

router = APIRouter()


@router.get("/internal/room", response_class=JSONResponse)
async def get_rooms_by_home_id(
    request: Request,
    home_id: int = Query(..., description="Home ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    内部 API：获取指定 home_id 下的所有房间
    从 Household Server 获取房间列表
    """
    get_request_id(request)
    try:
        # 调用 Household Server 的 API
        rooms = await _fetch_rooms_from_household_server(home_id)
        
        return success_response(data=rooms)
    
    except httpx.HTTPStatusError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Household Server returned error: {e.response.status_code}")
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except httpx.ConnectError:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Failed to connect to Household Server")
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching rooms from Household Server: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)


async def _fetch_rooms_from_household_server(home_id: int) -> list[dict]:
    """
    从 Household Server 获取房间列表
    """
    url = f"{settings.HOUSEHOLD_SERVER_URL}/api/v1/household/room"
    params = {"home_id": home_id}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        response_data = response.json()
        
        # 解析响应数据
        # Household Server 返回格式：{"internal_code": 200, "data": [...]}
        if isinstance(response_data, dict) and "data" in response_data:
            return response_data["data"]
        
        return []


# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

