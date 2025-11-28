from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.item_model import Item, ItemCategory
from app.models.cabinet_model import Cabinet
from app.models.category_model import Category
from app.schemas.warehouse_request import CreateItemRequest
from app.schemas.warehouse_response import ItemResponse
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header
from app.utils.util_file import save_base64_image
from app.utils.util_log import create_log
from app.models.log_model import StateType, ItemType, LogType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 路由入口
@router.post("/", response_class=JSONResponse)
async def create(
    request_data: CreateItemRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    try:
        # 統一錯誤檢查
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            return validation_error
        
        # 處理 base64 圖片（如果提供）
        if request_data.photo:
            photo_url, error_msg = save_base64_image(request_data.photo)
            if not photo_url:
                # 圖片處理失敗，返回錯誤
                return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
            # 將 URL 保存到 request_data 中，後續創建時使用
            request_data.photo = photo_url
        
        # 創建物品資料
        new_item = await _create_db_item(request_data, db)
        
        # 建立操作日誌
        log_result = await create_log(
            db=db,
            home_id=request_data.home_id,
            state=StateType.CREATE,
            item_type=ItemType.ITEM,
            user_name=request_data.user_name,
            operate_type=None,  # create 操作不需要 operate_type
            log_type=LogType.NORMAL,
        )
        if not log_result:
            logging.getLogger(__name__).warning("Failed to create item log for item_id=%s", str(new_item.id))
        
        # 產生響應資料
        response_data = ItemResponse.model_validate(new_item).model_dump(
            mode="json",
            exclude_none=True,
        )
        return success_response(data=response_data)

    except SQLAlchemyError as e:
        if db.in_transaction():
            await db.rollback()
        logger.error(f"SQLAlchemyError in create item: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_42)
    except Exception as e:
        if db.in_transaction():
            await db.rollback()
        logger.error(f"Exception in create item: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_42)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: CreateItemRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.name or not request_data.name.strip():
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_42)
    
    # 如果提供了 cabinet_id，檢查 Cabinet 是否存在並驗證
    if request_data.cabinet_id is not None:
        result = await db.execute(
            select(Cabinet).where(Cabinet.id == request_data.cabinet_id)
        )
        cabinet = result.scalar_one_or_none()
        if not cabinet:
            return _error_handle(ServerErrorCode.CABINET_NOT_FOUND_42)
        
        # 驗證 cabinet 的 home_id 是否與請求中的匹配
        if cabinet.home_id != request_data.home_id:
            return _error_handle(ServerErrorCode.CABINET_NOT_FOUND_42)
        
        # 如果提供了 room_id，驗證它是否與 cabinet 的 room_id 匹配
        if request_data.room_id is not None:
            if cabinet.room_id != request_data.room_id:
                return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        # 如果沒有提供 room_id，但 cabinet 有 room_id，使用 cabinet 的 room_id
        elif cabinet.room_id is not None:
            request_data.room_id = cabinet.room_id
    
    # 檢查分類是否存在（如果提供了分類）
    if request_data.category_ids:
        for category_id in request_data.category_ids:
            result = await db.execute(
                select(Category).where(Category.id == category_id)
            )
            category = result.scalar_one_or_none()
            if not category:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_42)

    return None

# 創建物品資料
async def _create_db_item(
    request_data: CreateItemRequest,
    db: AsyncSession
) -> Item:
    """創建物品資料"""
    new_item = Item(
        cabinet_id=request_data.cabinet_id,
        room_id=request_data.room_id,
        home_id=request_data.home_id,
        name=request_data.name,
        description=request_data.description,
        quantity=request_data.quantity,
        min_stock_alert=request_data.min_stock_alert,
        photo=request_data.photo
    )
    db.add(new_item)
    await db.flush()
    
    # 添加分類關聯（如果提供了分類）
    if request_data.category_ids:
        for category_id in request_data.category_ids:
            item_category = ItemCategory(
                item_id=new_item.id,
                category_id=category_id
            )
            db.add(item_category)
    
    await db.commit()
    await db.refresh(new_item)
    
    # 重新加載關聯數據
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.categories))
        .where(Item.id == new_item.id)
    )
    return result.scalar_one()

