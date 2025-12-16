from fastapi import APIRouter
from . import health
from .cabinet import router as cabinet_router
from .item import router as item_router
from .category import router as category_router
from .record import router as record_router

warehouse_router = APIRouter()

# 注册各个子路由
warehouse_router.include_router(cabinet_router, prefix="/cabinet", tags=["cabinet"])
warehouse_router.include_router(item_router, prefix="/item", tags=["item"])
warehouse_router.include_router(category_router, prefix="/category", tags=["category"])
warehouse_router.include_router(record_router, prefix="/record", tags=["record"])

# 为了保持向后兼容，创建一个 warehouse 对象
class WarehouseModule:
    router = warehouse_router

warehouse = WarehouseModule()