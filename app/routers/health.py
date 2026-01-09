from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.core.core_config import settings

router = APIRouter()

# 路由入口
@router.get("/")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        # 檢查資料庫連接
        await db.execute(text("SELECT 1"))
        
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
                    "endpoints": {
                        "root": f"{base_url}/",
                        "health": f"{base_url}/health",
                        "warehouse_router": f"{base_url}{settings.API_PREFIX}",
                        "warehouse_health": f"{base_url}{settings.API_PREFIX}/health"
                    }
                }
            )

    except SQLAlchemyError:
        return error_response(ServerErrorCode.WAREHOUSE_SERVICE_FAILED_40)
    except Exception:
        return error_response(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

