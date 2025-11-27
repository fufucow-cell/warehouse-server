from fastapi import APIRouter
from .internal_room import router as internal_room_router

# 创建主路由
router = APIRouter()

# 注册各个子路由
router.include_router(internal_room_router)

__all__ = ["router"]

