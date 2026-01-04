from typing import Optional, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from app.table import Item, ItemCabinetQuantity
from app.schemas.item_request import UpdateItemRequestModel, CabinetInfo, CabinetUpdateInfo, CategoryInfo, CategoryUpdateInfo
from app.schemas.item_response import ItemResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.services.item.item_read_service import build_item_response, get_cabinet_info, get_category_info
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_file import delete_uploaded_file, validate_base64_image, save_base64_image
from app.utils.util_uuid import uuid_to_str

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Update ====================
async def update_item(
    request_model: UpdateItemRequestModel,
    db: AsyncSession
) -> ItemResponseModel:
    result = await db.execute(
        select(Item).where(
            Item.id == uuid_to_str(request_model.id),
            Item.household_id == uuid_to_str(request_model.household_id)
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    old_item_model = await build_item_response(item, request_model.household_id, db)
    
    # 處理照片更新邏輯
    _update_item_photo(item, request_model.photo)
    
    # 處理 cabinet_id 更新
    cabinet_info = await _update_item_cabinet(item, request_model, db)
    
    # 處理 category_id 更新
    category_info = await _update_item_category(item, request_model, db)
    
    # name 不能為 None
    if request_model.name is not None:
        if request_model.name == "":
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        trimmed_name = request_model.name.strip()

        if len(trimmed_name) == 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        item.name = trimmed_name
    
    if request_model.description is not None:
        if request_model.description == "":
            item.description = None
        else:
            item.description = request_model.description
    # 處理 quantity 更新：更新 item_cabinet_quantity 表
    if request_model.quantity is not None:
        if request_model.quantity < 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        # 處理 quantity 更新：需要指定 cabinet_id 或使用第一個現有的
        if 'cabinet_id' in request_model.model_fields_set and request_model.cabinet_id is not None:
            # 使用指定的 cabinet_id
            qty_result = await db.execute(
                select(ItemCabinetQuantity).where(
                    ItemCabinetQuantity.item_id == item.id,
                    ItemCabinetQuantity.cabinet_id == uuid_to_str(request_model.cabinet_id)
                )
            )
            item_qty = qty_result.scalar_one_or_none()
            if item_qty:
                item_qty.quantity = request_model.quantity
                item_qty.updated_at = datetime.now(UTC_PLUS_8)
            else:
                # 創建新的 item_cabinet_quantity 記錄
                now_utc8 = datetime.now(UTC_PLUS_8)
                item_qty = ItemCabinetQuantity(
                    household_id=item.household_id,
                    item_id=item.id,
                    cabinet_id=uuid_to_str(request_model.cabinet_id),
                    quantity=request_model.quantity,
                    created_at=now_utc8,
                    updated_at=now_utc8,
                )
                db.add(item_qty)
        else:
            # 如果沒有指定 cabinet_id，更新第一個找到的 item_cabinet_quantity
            qty_result = await db.execute(
                select(ItemCabinetQuantity).where(
                    ItemCabinetQuantity.item_id == item.id
                ).limit(1)
            )
            item_qty = qty_result.scalar_one_or_none()
            if item_qty:
                item_qty.quantity = request_model.quantity
                item_qty.updated_at = datetime.now(UTC_PLUS_8)
            # 如果沒有現有的 item_cabinet_quantity，且沒有指定 cabinet_id，則無法更新 quantity
    if request_model.min_stock_alert is not None:
        if request_model.min_stock_alert < 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        item.min_stock_alert = request_model.min_stock_alert
    
    # Update updated_at to UTC+8 timezone
    item.updated_at = datetime.now(UTC_PLUS_8)
    
    await db.commit()
    new_item_model = await build_item_response(item, request_model.household_id, db)
    await _gen_record(old_item_model, new_item_model, request_model, cabinet_info, category_info, db)
    return new_item_model


# ==================== Private Methods ====================

# 處理照片更新邏輯
# None: 不更新照片（保持原樣）
# 空字串 "": 移除照片（刪除舊照片，設置為 None）
# 有值: 更新照片（驗證 base64，保存為文件，刪除舊照片，設置新照片 URL）
def _update_item_photo(
    item: Item,
    photo: Optional[str]
) -> None:
    if photo is not None:
        if item.photo is not None:
            delete_uploaded_file(cast(str, item.photo))

        if photo == "":
            item.photo = None
        else:
            if not validate_base64_image(photo):
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
            
            photo_url = save_base64_image(photo)

            if not photo_url:
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
            
            item.photo = photo_url


# 返回 old 和 new 的 cabinet 資訊
async def _update_item_cabinet(
    item: Item,
    request_model: UpdateItemRequestModel,
    db: AsyncSession
) -> CabinetUpdateInfo:
    # 從 item_cabinet_quantity 表獲取舊的 cabinet_id（使用第一個找到的）
    old_cabinet_quantities_query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.item_id == item.id
    ).limit(1)
    old_cabinet_quantities_result = await db.execute(old_cabinet_quantities_query)
    old_cabinet_quantity = old_cabinet_quantities_result.scalar_one_or_none()
    old_cabinet_id_uuid = cast(Optional[UUID], old_cabinet_quantity.cabinet_id) if old_cabinet_quantity else None
    
    old_household_id_uuid = cast(UUID, item.household_id)
    old_cabinet_info_dict = await get_cabinet_info(old_cabinet_id_uuid, old_household_id_uuid, db)
    old_cabinet_info = CabinetInfo(
        cabinet_id=old_cabinet_info_dict.get("cabinet_id"),
        cabinet_name=old_cabinet_info_dict.get("cabinet_name"),
        room_id=old_cabinet_info_dict.get("room_id")
    )
    
    # 處理 cabinet_id 和 quantity 更新（通過 item_cabinet_quantity 表）
    new_cabinet_id: Optional[UUID] = None
    if 'cabinet_id' in request_model.model_fields_set and 'quantity' in request_model.model_fields_set:
        # 如果同時更新 cabinet_id 和 quantity
        if request_model.cabinet_id is not None and request_model.quantity is not None:
            # 查找或創建 item_cabinet_quantity 記錄
            existing_qty_query = select(ItemCabinetQuantity).where(
                ItemCabinetQuantity.item_id == item.id,
                ItemCabinetQuantity.cabinet_id == uuid_to_str(request_model.cabinet_id)
            )
            existing_qty_result = await db.execute(existing_qty_query)
            existing_qty = existing_qty_result.scalar_one_or_none()
            
            if existing_qty:
                # 更新現有記錄
                existing_qty.quantity = request_model.quantity
                existing_qty.updated_at = datetime.now(UTC_PLUS_8)
            else:
                # 創建新記錄
                new_qty = ItemCabinetQuantity(
                    household_id=item.household_id,
                    item_id=item.id,
                    cabinet_id=uuid_to_str(request_model.cabinet_id),
                    quantity=request_model.quantity,
                    created_at=datetime.now(UTC_PLUS_8),
                    updated_at=datetime.now(UTC_PLUS_8),
                )
                db.add(new_qty)
            
            new_cabinet_id = cast(UUID, request_model.cabinet_id)
        elif request_model.cabinet_id is None:
            # 如果 cabinet_id 為 None，移除所有 item_cabinet_quantity 記錄
            delete_qty_query = sql_delete(ItemCabinetQuantity).where(
                ItemCabinetQuantity.item_id == item.id
            )
            await db.execute(delete_qty_query)
            new_cabinet_id = None
    elif 'quantity' in request_model.model_fields_set and request_model.quantity is not None:
        # 只更新 quantity，使用第一個現有的 cabinet
        if old_cabinet_quantity:
            old_cabinet_quantity.quantity = request_model.quantity
            old_cabinet_quantity.updated_at = datetime.now(UTC_PLUS_8)
            new_cabinet_id = cast(UUID, old_cabinet_quantity.cabinet_id)
        else:
            # 沒有現有的 cabinet，需要 cabinet_id 才能創建
            new_cabinet_id = None
    else:
        # 沒有更新，使用舊的 cabinet_id
        new_cabinet_id = old_cabinet_id_uuid
    
    household_id_uuid = cast(UUID, item.household_id)
    new_cabinet_info_dict = await get_cabinet_info(new_cabinet_id, household_id_uuid, db)
    new_cabinet_info = CabinetInfo(
        cabinet_id=new_cabinet_info_dict.get("cabinet_id"),
        cabinet_name=new_cabinet_info_dict.get("cabinet_name"),
        room_id=new_cabinet_info_dict.get("room_id")
    )
    
    return CabinetUpdateInfo(
        old=old_cabinet_info,
        new=new_cabinet_info
    )


async def _update_item_category(
    item: Item,
    request_model: UpdateItemRequestModel,
    db: AsyncSession
) -> CategoryUpdateInfo:
    old_category_id_uuid = cast(Optional[UUID], item.category_id) if item.category_id else None
    old_category_info_dict = await get_category_info(old_category_id_uuid, cast(UUID, item.household_id), db)
    old_category_info = CategoryInfo(
        category_id=old_category_info_dict.get("category_id"),
        level_name=old_category_info_dict.get("level_name")
    )
    
    # 處理 category_id 更新：如果提供空字符串或 None，則移除 category
    if 'category_id' in request_model.model_fields_set:
        item.category_id = uuid_to_str(request_model.category_id)
    
    new_category_id_uuid = cast(Optional[UUID], item.category_id) if item.category_id else None
    new_category_info_dict = await get_category_info(new_category_id_uuid, cast(UUID, item.household_id), db)
    new_category_info = CategoryInfo(
        category_id=new_category_info_dict.get("category_id"),
        level_name=new_category_info_dict.get("level_name")
    )
    return CategoryUpdateInfo(
        old=old_category_info,
        new=new_category_info
    )


async def _gen_record(
    old_item_model: ItemResponseModel,
    new_item_model: ItemResponseModel,
    request_model: UpdateItemRequestModel,
    cabinet_info: CabinetUpdateInfo,
    category_info: CategoryUpdateInfo,
    db: AsyncSession
) -> None:
    # 檢測哪些字段有變化
    name_changed = request_model.name is not None and request_model.name.strip() != old_item_model.name
    # description 變更檢測：如果新值是空字串且舊值是 None，則視為無變化
    description_changed = False
    if request_model.description is not None:
        if request_model.description == "":
            # 如果新值是空字串，但舊值是 None，則視為無變化
            description_changed = old_item_model.description is not None
        else:
            description_changed = request_model.description != old_item_model.description
    quantity_changed = request_model.quantity is not None and request_model.quantity != old_item_model.quantity
    min_stock_alert_changed = request_model.min_stock_alert is not None and request_model.min_stock_alert != old_item_model.min_stock_alert
    # photo 變更檢測：如果新值是空字串且舊值是 None，則視為無變化
    photo_changed = False
    if request_model.photo is not None:
        if request_model.photo == "":
            # 如果新值是空字串，但舊值是 None，則視為無變化
            photo_changed = old_item_model.photo is not None
        else:
            # photo 有值（base64），視為變更
            photo_changed = True
    # cabinet_changed 檢測：使用 cabinet_info 中的資訊
    cabinet_changed = False
    # 檢查 cabinet_id 是否在請求中被設置，並且值有變化
    if 'cabinet_id' in request_model.model_fields_set:
        # 比較舊值和新值，如果不同則表示有變化
        cabinet_changed = cabinet_info.old.cabinet_id != cabinet_info.new.cabinet_id
    # 如果 cabinet_id 不在 model_fields_set 中，表示沒有在請求中設置，不需要檢查變化
    
    # category_changed 檢測：使用 category_info 中的資訊
    category_changed = False
    # 檢查 category_id 是否在請求中被設置，並且值有變化
    if 'category_id' in request_model.model_fields_set:
        category_changed = category_info.old.category_id != category_info.new.category_id
    # 如果 category_id 不在 model_fields_set 中，表示沒有在請求中設置，不需要檢查變化
    has_changes = name_changed or description_changed or quantity_changed or min_stock_alert_changed or photo_changed or cabinet_changed or category_changed
    
    if has_changes:
        # 獲取新值：如果請求值是空字串，記錄空字串；否則使用 new_item_model 的值
        def get_new_value(request_val, new_model_val, changed):
            if not changed:
                return None
            # 如果請求值是空字串，記錄空字串（即使 new_model_val 是 None）
            if request_val == "":
                return ""
            # 否則使用 new_model 的值
            return new_model_val
        
        await create_record(
            CreateRecordRequestModel(
                household_id=request_model.household_id,
                user_name=request_model.user_name,
                operate_type=OperateType.UPDATE.value,
                entity_type=EntityType.ITEM.value,
                item_name_old=old_item_model.name if name_changed else None,
                item_name_new=new_item_model.name if name_changed else None,
                item_description_old=old_item_model.description if description_changed else None,
                item_description_new=get_new_value(request_model.description, new_item_model.description, description_changed),
                item_photo_old=old_item_model.photo if photo_changed else None,
                item_photo_new=get_new_value(request_model.photo, new_item_model.photo, photo_changed),
                cabinet_name_old=cabinet_info.old.cabinet_name if cabinet_changed else None,
                cabinet_name_new="" if (cabinet_changed and cabinet_info.new.cabinet_id is None) else (cabinet_info.new.cabinet_name if cabinet_changed else None),
                category_name_old=category_info.old.level_name if category_changed else None,
                category_name_new="" if (category_changed and category_info.new.category_id is None) else (category_info.new.level_name if category_changed else None),
                quantity_count_old=old_item_model.quantity if quantity_changed else None,
                quantity_count_new=new_item_model.quantity if quantity_changed else None,
                min_stock_count_old=old_item_model.min_stock_alert if min_stock_alert_changed else None,
                min_stock_count_new=new_item_model.min_stock_alert if min_stock_alert_changed else None,
            ),
            db
        )

