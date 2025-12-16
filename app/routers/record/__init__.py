"""
Warehouse Record Routers
处理记录相关的路由
"""
from fastapi import APIRouter
from .record_create import router as record_create_router
from .record_read import router as record_read_router
from .record_delete import router as record_delete_router

# 创建主路由
router = APIRouter()

# 注册各个子路由
router.include_router(record_create_router, tags=["record"])
router.include_router(record_read_router, tags=["record"])
router.include_router(record_delete_router, tags=["record"])

