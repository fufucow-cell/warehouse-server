from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode

router = APIRouter()

# 路由入口
@router.get("/health")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        # 檢查資料庫連接
        await db.execute(text("SELECT 1"))
        
        return success_response(
            data={
                "status": "healthy",
                "service": "warehouse-api"
            }
        )

    except SQLAlchemyError:
        return _error_handle(ServerErrorCode.WAREHOUSE_SERVICE_FAILED_40)
    except Exception:
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_40)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

