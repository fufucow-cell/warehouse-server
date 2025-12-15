from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from app.routers import health, warehouse
from app.core.core_config import settings
from app.db.session import get_db
from app.utils.util_error_handle import (
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler
)
from app.middleware.log_setup import DevLoggingMiddleware

app = FastAPI(
    title="Warehouse Server",
    description="Warehouse domain service (placeholder until DB is ready)",
    version="0.1.0"
)

# 注意：所有日志（请求日志、错误日志）已在 API Gateway 统一记录，此处不再记录

# 開發用 Console 日誌中間件（僅在配置為 true 時生效）
app.add_middleware(DevLoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理器 - 统一响应格式
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)  # 捕获所有未处理的异常

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(warehouse.router, prefix="/api/v1/warehouse", tags=["warehouse"])

# 静态文件服务 - 用于访问上传的文件
upload_dir = Path(__file__).parent / settings.UPLOAD_DIR
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount(f"/{settings.UPLOAD_DIR}", StaticFiles(directory=str(upload_dir)), name="uploads")

@app.get("/")
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    return await health.health_check(request, db)

