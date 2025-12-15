from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from fastapi.responses import JSONResponse
from app.db.session import get_db
from app.table.item_model import Item, ItemCategory
from app.table.cabinet_model import Cabinet
from app.table.category_model import Category
from app.schemas.item_request import CreateItemRequestModel
from app.schemas.item_response import ItemResponseModel
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header
from app.utils.util_file import save_base64_image
from app.utils.util_log import create_log
from app.table.log_model import StateType, ItemType, LogType
from app.utils.util_log import log_request_start, log_request_step, log_request_success, log_request_error
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 路由入口
@router.post("/", response_class=JSONResponse)
async def create(
    request_data: CreateItemRequestModel,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    get_request_id(request)
    sequence = log_request_start(request, "create_item", {"item_name": request_data.name, "household_id": str(request_data.household_id)})
    
    try:
        # [流水號 X.1] 統一錯誤檢查
        log_request_step(sequence, request, "1.1", "validation_check")
        validation_error = await _error_check(request, request_data, db)
        if validation_error:
            log_request_error(sequence, request, "create_item", Exception("Validation failed"))
            return validation_error
        
        # [流水號 X.2] 處理 base64 圖片（如果提供）
        if request_data.photo:
            log_request_step(sequence, request, "1.2", "process_image")
            photo_url = save_base64_image(request_data.photo)
            if not photo_url:
                log_request_error(sequence, request, "create_item", Exception("Image processing failed"))
                return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42, request)
            request_data.photo = photo_url
            log_request_step(sequence, request, "1.2.1", "image_saved", {"photo_url": photo_url})
        
        # [流水號 X.3] 創建物品資料
        log_request_step(sequence, request, "1.3", "create_db_item")
        new_item = await _create_db_item(request_data, db)
        
        # [流水號 X.4] 建立操作日誌
        log_request_step(sequence, request, "1.4", "create_log", {"item_id": str(new_item.id)})
        log_result = await create_log(
            db=db,
            home_id=request_data.household_id,
            state=StateType.CREATE,
            item_type=ItemType.ITEM,
            user_name=request_data.user_name,
            operate_type=None,
            log_type=LogType.NORMAL,
        )
        if not log_result:
            logging.getLogger(__name__).warning("Failed to create item log for item_id=%s", str(new_item.id))
            log_request_step(sequence, request, "1.4.1", "log_creation_failed")
        
        # [流水號 X.5] 產生響應資料
        log_request_step(sequence, request, "1.5", "prepare_response")
        response_data = ItemResponseModel.model_validate(new_item).model_dump(
            mode="json",
            exclude_none=True,
        )
        
        log_request_success(sequence, request, "create_item", {"item_id": str(new_item.id)})
        return success_response(data=response_data, request=request)

    except SQLAlchemyError as e:
        if db.in_transaction():
            await db.rollback()
        log_request_error(sequence, request, "create_item", e)
        logger.error(f"SQLAlchemyError in create item: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_42, request)
    except Exception as e:
        if db.in_transaction():
            await db.rollback()
        log_request_error(sequence, request, "create_item", e)
        logger.error(f"Exception in create item: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_42, request)

# 自定義錯誤處理
def _error_handle(internal_code: int, request: Optional[Request] = None) -> JSONResponse:
    return error_response(internal_code=internal_code, request=request)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: CreateItemRequestModel,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.name or not request_data.name.strip():
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42, request)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_42, request)
        
    # 如果提供了 cabinet_id，檢查 Cabinet 是否存在並驗證
    if request_data.cabinet_id is not None:
        result = await db.execute(
            select(Cabinet).where(Cabinet.id == request_data.cabinet_id)
        )
        cabinet = result.scalar_one_or_none()
        if not cabinet:
            return _error_handle(ServerErrorCode.CABINET_NOT_FOUND_42, request)
        
        # 驗證 cabinet 的 household_id 是否與請求中的匹配
        if cabinet.household_id != request_data.household_id:
            return _error_handle(ServerErrorCode.CABINET_NOT_FOUND_42, request)
        
        # 如果提供了 room_id，驗證它是否與 cabinet 的 room_id 匹配
        if request_data.room_id is not None:
            if cabinet.room_id != request_data.room_id:
                return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42, request)
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
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_42, request)

    return None

# 創建物品資料
async def _create_db_item(
    request_data: CreateItemRequestModel,
    db: AsyncSession
) -> Item:
    """創建物品資料"""
    new_item = Item(
        cabinet_id=request_data.cabinet_id,
        room_id=request_data.room_id,
        household_id=request_data.household_id,
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

