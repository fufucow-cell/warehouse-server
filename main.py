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
app = FastAPI(
    title="Warehouse Server",
    description="Warehouse domain service",
    version="1.0.0",
    redirect_slashes=True  # 启用自动重定向，支持带/不带末尾斜杠的路径
)

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
async def root(request: Request):
    """根路径，返回简单的服务信息，不依赖数据库连接"""
    from app.utils.util_response import success_response
    return success_response(
        data={
            "status": "running",
            "service": "warehouse-api",
            "version": "1.0.0"
        },
        request=request
    )

