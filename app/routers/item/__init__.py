from fastapi import APIRouter
from .item_create import router as item_create_router
from .item_create_smart import router as item_create_smart_router
from .item_delete import router as item_delete_router
from .item_read import router as item_read_router
from .item_update_normal import router as item_update_normal_router
from .item_update_position import router as item_update_position_router
from .item_update_quantity import router as item_update_quantity_router

# 创建主路由
router = APIRouter()

# 注册各个子路由
router.include_router(item_create_router, tags=["item-create"])
router.include_router(item_create_smart_router, prefix="/smart", tags=["item-create"])
router.include_router(item_delete_router)
router.include_router(item_read_router)
router.include_router(item_update_normal_router, prefix="/normal", tags=["item-update"])
router.include_router(item_update_position_router, prefix="/position", tags=["item-update"])
router.include_router(item_update_quantity_router, prefix="/quantity", tags=["item-update"])

