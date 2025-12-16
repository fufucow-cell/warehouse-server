from fastapi import APIRouter
from .category_create import router as category_create_router
from .category_delete import router as category_delete_router
from .category_read import router as category_read_router
from .category_update import router as category_update_router

# 创建主路由
router = APIRouter()

# 注册各个子路由
router.include_router(category_create_router)
router.include_router(category_delete_router)
router.include_router(category_read_router)
router.include_router(category_update_router)

