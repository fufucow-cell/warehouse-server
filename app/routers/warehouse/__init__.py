from fastapi import APIRouter
from .cabinet import router as cabinet_router
from .item import router as item_router
from .category import router as category_router
from .internal import router as internal_router

router = APIRouter()

# 注册各个子路由
router.include_router(cabinet_router, prefix="/cabinet", tags=["cabinet"])
router.include_router(item_router, prefix="/item", tags=["item"])
router.include_router(category_router, prefix="/category", tags=["category"])
router.include_router(internal_router, tags=["internal"])

__all__ = ["router"]
