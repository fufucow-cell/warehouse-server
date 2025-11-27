from fastapi import APIRouter
from .cabinet_create import router as cabinet_create_router
from .cabinet_delete import router as cabinet_delete_router
from .cabinet_fetch import router as cabinet_fetch_router
from .cabinet_update import router as cabinet_update_router

# 创建主路由
router = APIRouter()

# 注册各个子路由
router.include_router(cabinet_create_router)
router.include_router(cabinet_delete_router)
router.include_router(cabinet_fetch_router)
router.include_router(cabinet_update_router)

__all__ = ["router"]

