from fastapi import APIRouter
from .item_create import router as item_create_router
from .item_delete import router as item_delete_router
from .item_fetch import router as item_fetch_router
from .item_update import router as item_update_router

# 创建主路由
router = APIRouter()

# 注册各个子路由
router.include_router(item_create_router)
router.include_router(item_delete_router)
router.include_router(item_fetch_router)
router.include_router(item_update_router)

__all__ = ["router"]

