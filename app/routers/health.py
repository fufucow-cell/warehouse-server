import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.core.core_config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# 路由入口
@router.get("/")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 檢查資料庫連接狀態
    sql_connect_status = False
    sql_error_msg = None
    try:
        await db.execute(text("SELECT 1"))
        sql_connect_status = True
    except SQLAlchemyError as e:
        sql_connect_status = False
        sql_error_msg = str(e)
        logger.error(f"Database connection error: {e}", exc_info=True)
    except Exception as e:
        sql_connect_status = False
        sql_error_msg = str(e)
        logger.error(f"Unexpected database error: {e}", exc_info=True)
    
    # 獲取 base URL
    base_url = str(request.base_url).rstrip('/')
    
    # 判斷是從哪個 router 調用的
    path = request.url.path.rstrip('/')
    is_warehouse_router = path.startswith(settings.API_PREFIX)
    
    if is_warehouse_router:
        # Warehouse router 的 health check
        return success_response(
            data={
                "status": "healthy",
                "service": "warehouse-api",
                "router": "warehouse",
                "sql_connect_status": sql_connect_status,
                "sql_error": sql_error_msg if not sql_connect_status else None,
                "endpoints": {
                    "root": f"{base_url}{settings.API_PREFIX}",
                    "health": f"{base_url}{settings.API_PREFIX}/health",
                    "cabinet": f"{base_url}{settings.API_PREFIX}/cabinet",
                    "item": f"{base_url}{settings.API_PREFIX}/item",
                    "category": f"{base_url}{settings.API_PREFIX}/category",
                    "record": f"{base_url}{settings.API_PREFIX}/record"
                }
            }
        )
    else:
        # Root router 的 health check
        return success_response(
            data={
                "status": "healthy",
                "service": "warehouse-api",
                "router": "root",
                "sql_connect_status": sql_connect_status,
                "sql_error": sql_error_msg if not sql_connect_status else None,
                "endpoints": {
                    "root": f"{base_url}/",
                    "health": f"{base_url}/health",
                    "warehouse_router": f"{base_url}{settings.API_PREFIX}",
                    "warehouse_health": f"{base_url}{settings.API_PREFIX}/health"
                }
            }
        )
