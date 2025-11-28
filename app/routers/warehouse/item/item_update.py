from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from fastapi.responses import JSONResponse
from app.core.core_database import get_db
from app.models.item_model import Item, ItemCategory
from app.models.category_model import Category
from app.schemas.warehouse_request import UpdateItemRequest
from app.schemas.warehouse_response import ItemResponse
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from typing import List
from app.utils.util_request import get_request_id, get_user_id_from_header
from app.models.cabinet_model import Cabinet
from app.utils.util_file import save_base64_image, delete_uploaded_file
from app.utils.util_log import create_log
from app.models.log_model import StateType, ItemType, OperateType, LogType
import logging

router = APIRouter()

# 路由入口
@router.put("/", response_class=JSONResponse)
async def update(
    request_data: UpdateItemRequest,
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
            # 先獲取舊圖片 URL（用於刪除）
            result = await db.execute(
                select(Item).where(Item.id == request_data.item_id)
            )
            old_item = result.scalar_one_or_none()
            old_photo_url = old_item.photo if old_item else None
            
            # 保存新圖片
            photo_url, error_msg = save_base64_image(request_data.photo)
            if not photo_url:
                # 圖片處理失敗，返回錯誤
                return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
            
            # 刪除舊圖片（如果存在）
            if old_photo_url:
                delete_uploaded_file(old_photo_url)
            
            # 將 URL 保存到 request_data 中，後續更新時使用
            request_data.photo = photo_url
        
        # 獲取舊的 item 信息（用於檢測字段變化）
        old_result = await db.execute(
            select(Item).where(Item.id == request_data.item_id)
        )
        old_item = old_result.scalar_one()
        
        # 立即保存舊值（避免 SQLAlchemy 對象被修改後影響比較）
        old_values = {
            'name': old_item.name,
            'description': old_item.description,
            'quantity': old_item.quantity,
            'min_stock_alert': old_item.min_stock_alert,
            'cabinet_id': old_item.cabinet_id,
            'room_id': old_item.room_id,
            'home_id': old_item.home_id,
            'photo': old_item.photo
        }
        
        # 修改物品資料
        updated_item = await _update_db_item(request_data, db)
        
        # 建立操作日誌
        operate_types = _detect_operate_types(request_data, old_values, updated_item)
        log_result = await create_log(
            db=db,
            home_id=updated_item.home_id,
            state=StateType.MODIFY,
            item_type=ItemType.ITEM,
            user_name=request_data.user_name,
            operate_type=operate_types,
            log_type=LogType.NORMAL,
        )
        if not log_result:
            logging.getLogger(__name__).warning("Failed to create item log for item_id=%s", str(updated_item.id))
        
        # 產生響應資料
        response_data = ItemResponse.model_validate(updated_item).model_dump(
            mode="json",
            exclude_none=True,
        )
        # 移除 url 字段（如果存在）
        response_data.pop("url", None)
        return success_response(data=response_data)

    except SQLAlchemyError:
        if db.in_transaction():
            await db.rollback()
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_42)
    except Exception:
        if db.in_transaction():
            await db.rollback()
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_42)

# 自定義錯誤處理
def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)

# 自定義錯誤檢查
async def _error_check(
    request: Request,
    request_data: UpdateItemRequest,
    db: AsyncSession
) -> Optional[JSONResponse]:
    # 檢查必要參數
    if not request_data.item_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if request_data.name is not None and not request_data.name.strip():
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
    user_id = get_user_id_from_header(request)
    if not user_id:
        return _error_handle(ServerErrorCode.UNAUTHORIZED_42)
    
    # 檢查 Item 是否存在
    result = await db.execute(
        select(Item).where(Item.id == request_data.item_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        return _error_handle(ServerErrorCode.ITEM_NOT_FOUND_42)
    
    # 驗證 item 的 home_id 是否與請求中的 home_id 匹配
    if item.home_id != request_data.home_id:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 如果提供了 new_cabinet_id，需要驗證 new_cabinet_id 是否存在且屬於該家庭
    if request_data.new_cabinet_id is not None:
        # 檢查 new_cabinet_id 是否存在
        result = await db.execute(
            select(Cabinet).where(Cabinet.id == request_data.new_cabinet_id)
        )
        new_cabinet = result.scalar_one_or_none()
        if not new_cabinet:
            return _error_handle(ServerErrorCode.CABINET_NOT_FOUND_42)
        
        # 驗證 new_cabinet 的 home_id 是否與 item 的 home_id 匹配
        if new_cabinet.home_id != item.home_id:
            return _error_handle(ServerErrorCode.CABINET_NOT_FOUND_42)
    
    # 檢查新分類是否存在（如果提供了新分類）
    if request_data.new_category_ids:
        for category_id in request_data.new_category_ids:
            result = await db.execute(
                select(Category).where(Category.id == category_id)
            )
            category = result.scalar_one_or_none()
            if not category:
                return _error_handle(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    return None

# 修改物品資料
async def _update_db_item(
    request_data: UpdateItemRequest,
    db: AsyncSession
) -> Item:
    """修改物品資料並返回更新後的 Item"""
    result = await db.execute(
        select(Item).where(Item.id == request_data.item_id)
    )
    item = result.scalar_one()
    
    # 更新 new_cabinet_id（如果提供）
    if request_data.new_cabinet_id is not None:
        item.cabinet_id = request_data.new_cabinet_id
    
    # 更新 new_room_id（如果提供）
    if request_data.new_room_id is not None:
        item.room_id = request_data.new_room_id
    
    if request_data.home_id is not None:
        item.home_id = request_data.home_id
    if request_data.name is not None:
        item.name = request_data.name
    if request_data.description is not None:
        item.description = request_data.description
    if request_data.quantity is not None:
        item.quantity = request_data.quantity
    if request_data.min_stock_alert is not None:
        item.min_stock_alert = request_data.min_stock_alert
    if request_data.photo is not None:
        item.photo = request_data.photo
    
    # 更新分類關聯（如果提供了新分類）
    if request_data.new_category_ids is not None:
        # 刪除現有的分類關聯
        await db.execute(
            delete(ItemCategory).where(ItemCategory.item_id == request_data.item_id)
        )
        # 添加新的分類關聯
        for category_id in request_data.new_category_ids:
            item_category = ItemCategory(
                item_id=request_data.item_id,
                category_id=category_id
            )
            db.add(item_category)
    
    await db.commit()
    await db.refresh(item)
    
    # 重新加載關聯數據（categories）
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.categories))
        .where(Item.id == request_data.item_id)
    )
    return result.scalar_one()


# 檢測操作類型
def _detect_operate_types(
    request_data: UpdateItemRequest,
    old_values: dict,
    updated_item: Item
) -> List[OperateType]:
    """檢測哪些字段被修改了，返回對應的 OperateType 列表"""
    operate_types: List[OperateType] = []
    
    # 檢查 name 是否被修改（使用保存的舊值進行比較）
    if request_data.name is not None:
        old_name = old_values['name'] if old_values['name'] is not None else ""
        new_name = request_data.name if request_data.name is not None else ""
        if old_name != new_name:
            operate_types.append(OperateType.NAME)
    
    # 檢查 description 是否被修改（使用保存的舊值進行比較）
    if request_data.description is not None:
        old_desc = old_values['description'] if old_values['description'] is not None else ""
        new_desc = request_data.description if request_data.description is not None else ""
        if old_desc != new_desc:
            operate_types.append(OperateType.DESCRIPTION)
    
    # 檢查 quantity 是否被修改（使用保存的舊值進行比較）
    if request_data.quantity is not None:
        if old_values['quantity'] != request_data.quantity:
            operate_types.append(OperateType.QUANTITY)
    
    # 檢查 min_stock_alert 是否被修改（使用保存的舊值進行比較）
    if request_data.min_stock_alert is not None:
        if old_values['min_stock_alert'] != request_data.min_stock_alert:
            operate_types.append(OperateType.MIN_STOCK_ALERT)
    
    # 檢查 photo 是否被修改（使用保存的舊值進行比較）
    if request_data.photo is not None:
        old_photo = old_values['photo'] if old_values['photo'] is not None else ""
        new_photo = request_data.photo if request_data.photo is not None else ""
        if old_photo != new_photo:
            operate_types.append(OperateType.PHOTO)
    
    # 檢查是否移動（cabinet_id, room_id 或 home_id 變化）
    cabinet_id_changed = False
    room_id_changed = False
    home_id_changed = False
    
    if request_data.new_cabinet_id is not None:
        # 使用保存的舊值進行比較
        if old_values['cabinet_id'] != request_data.new_cabinet_id:
            cabinet_id_changed = True
    
    if request_data.new_room_id is not None:
        # 使用保存的舊值進行比較
        if old_values['room_id'] != request_data.new_room_id:
            room_id_changed = True
    
    if request_data.home_id is not None:
        # 使用保存的舊值進行比較
        if old_values['home_id'] != request_data.home_id:
            home_id_changed = True
    
    if cabinet_id_changed or room_id_changed or home_id_changed:
        operate_types.append(OperateType.MOVE)
    
    return operate_types

