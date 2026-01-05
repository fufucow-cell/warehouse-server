from typing import List, Optional, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from app.table import Item, ItemCabinetQuantity
from app.table.cabinet import Cabinet
from app.schemas.item_request import (
    UpdateItemNormalRequestModel,
    UpdateItemQuantityRequestModel,
    UpdateItemPositionRequestModel,
    CabinetInfo,
    CabinetUpdateInfo,
    CategoryInfo,
    CategoryUpdateInfo
)
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

# ==================== Update Normal ====================
async def update_item_normal(
    request_model: UpdateItemNormalRequestModel,
    db: AsyncSession
) -> ItemResponseModel:
    result = await db.execute(
        select(Item).where(
            Item.id == uuid_to_str(request_model.item_id),
            Item.household_id == uuid_to_str(request_model.household_id)
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    old_item_model = await build_item_response(item, request_model.household_id, db)
    
    # 處理照片更新邏輯
    _update_item_photo(item, request_model.photo)
    
    # 處理 category_id 更新
    category_info = await _update_item_category_normal(item, request_model, db)
    
    # name 不能為空字串（如果提供）
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
    
    if request_model.min_stock_alert is not None:
        if request_model.min_stock_alert < 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        item.min_stock_alert = request_model.min_stock_alert
    
    # Update updated_at to UTC+8 timezone
    item.updated_at = datetime.now(UTC_PLUS_8)
    
    await db.commit()
    new_item_model = await build_item_response(item, request_model.household_id, db)
    
    # 獲取 cabinet_info（保持不變）
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
    cabinet_info = CabinetUpdateInfo(old=old_cabinet_info, new=old_cabinet_info)
    
    await _gen_record_normal(old_item_model, new_item_model, request_model, cabinet_info, category_info, db)
    return new_item_model


# ==================== Update Quantity ====================

async def update_item_quantity(
    request_model: UpdateItemQuantityRequestModel,
    db: AsyncSession
) -> None:
    household_id = uuid_to_str(request_model.household_id)
    result = await db.execute(
        select(Item).where(
            Item.id == uuid_to_str(request_model.item_id),
            Item.household_id == household_id
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)

    # 過濾出有效的 cabinet_id（不為 None）
    valid_cabinet_ids = [cab.cabinet_id for cab in request_model.cabinets if cab.cabinet_id is not None]
    
    # 查詢有效的 cabinets（cabinet_id 不為 None 的情況）
    cabinets_dict = {}
    if valid_cabinet_ids:
        cabinet_query = select(Cabinet).where(
            Cabinet.id.in_([uuid_to_str(cid) for cid in valid_cabinet_ids]),
            Cabinet.household_id == household_id
        )
        cabinet_result = await db.execute(cabinet_query)
        cabinets_list = cabinet_result.scalars().all()
        cabinets_dict = {uuid_to_str(cab.id): cab for cab in cabinets_list}
    
    # 查詢現有的 ItemCabinetQuantity 記錄
    quantity_query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.item_id == item.id,
    )
    quantity_result = await db.execute(quantity_query)
    quantities_list = quantity_result.scalars().all()
    # 使用 cabinet_id (可能是 None) 作為 key，None 用 "None" 字符串表示
    quantities_dict = {qty.cabinet_id if qty.cabinet_id is not None else None: qty for qty in quantities_list}
    
    # 保存 old quantities（在更新之前）
    old_quantities_dict = {qty.cabinet_id if qty.cabinet_id is not None else None: qty.quantity for qty in quantities_list}
    
    # 處理 quantity 更新：更新 item_cabinet_quantity 表
    now_utc8 = datetime.now(UTC_PLUS_8)
    
    cabinet_quantity_changes = []  # 保存變更資訊：[(cabinet_id, cabinet_name, old_quantity, new_quantity)]
    
    for req_cab in request_model.cabinets:
        # 處理 cabinet_id 為 None 的情況（未綁定櫥櫃）
        cabinet_id_str = None
        cabinet_name = None
        
        if req_cab.cabinet_id is not None:
            cabinet_id_str = uuid_to_str(req_cab.cabinet_id)
            cabinet = cabinets_dict.get(cabinet_id_str)
            if cabinet is None:
                # cabinet_id 存在但找不到對應的 cabinet，跳過
                continue
            cabinet_name = cabinet.name
        else:
            # cabinet_id 為 None，表示未綁定櫥櫃
            cabinet_name = None  # 未綁定櫥櫃沒有名稱
        
        # 使用 None 作為 key（當 cabinet_id 為 None 時）
        dict_key = cabinet_id_str if cabinet_id_str is not None else None
        item_qty = quantities_dict.get(dict_key)
        old_quantity = old_quantities_dict.get(dict_key, 0)
        new_quantity = req_cab.quantity
        
        if item_qty:
            # 更新現有記錄
            item_qty.quantity = new_quantity
            item_qty.updated_at = now_utc8
        else:
            # 創建新記錄
            new_qty = ItemCabinetQuantity(
                household_id=item.household_id,
                item_id=item.id,
                cabinet_id=cabinet_id_str,  # 可以是 None
                quantity=new_quantity,
                created_at=now_utc8,
                updated_at=now_utc8,
            )
            db.add(new_qty)
        
        # 只有在 quantity 有變化時才記錄
        if old_quantity != new_quantity:
            cabinet_quantity_changes.append((req_cab.cabinet_id, cabinet_name, old_quantity, new_quantity))
    
    item.updated_at = now_utc8
    await db.commit()
    new_item_model = await build_item_response(item, request_model.household_id, db)
    
    # 生成記錄（quantity 變化）
    await _gen_record_quantity(cabinet_quantity_changes, request_model, db)


# ==================== Update Position ====================
async def update_item_position(
    request_model: UpdateItemPositionRequestModel,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Item).where(
            Item.id == uuid_to_str(request_model.item_id),
            Item.household_id == uuid_to_str(request_model.household_id)
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    # 驗證每個 cabinet 請求
    for cabinet_req in request_model.cabinets:
        # 1. 驗證 old_cabinet_id（如果不為 None，則必須在 cabinet table 中存在且屬於同一個 household）
        if cabinet_req.old_cabinet_id is not None:
            old_cabinet_result = await db.execute(
                select(Cabinet).where(
                    Cabinet.id == uuid_to_str(cabinet_req.old_cabinet_id),
                    Cabinet.household_id == uuid_to_str(request_model.household_id)
                )
            )
            old_cabinet = old_cabinet_result.scalar_one_or_none()
            if not old_cabinet:
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        
        # 2. 驗證 new_cabinet_id（如果不為 None，則必須在 cabinet table 中存在且屬於同一個 household）
        if cabinet_req.new_cabinet_id is not None:
            new_cabinet_result = await db.execute(
                select(Cabinet).where(
                    Cabinet.id == uuid_to_str(cabinet_req.new_cabinet_id),
                    Cabinet.household_id == uuid_to_str(request_model.household_id)
                )
            )
            new_cabinet = new_cabinet_result.scalar_one_or_none()
            if not new_cabinet:
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        
        # 3. 驗證 ItemCabinetQuantity 中 old_cabinet_id 的 quantity 存在
        # 如果 old_cabinet_id 為 None，則查詢 cabinet_id IS NULL 的記錄（未綁定櫃位）
        old_qty_query = select(ItemCabinetQuantity).where(
            ItemCabinetQuantity.item_id == item.id
        )
        if cabinet_req.old_cabinet_id is not None:
            old_qty_query = old_qty_query.where(
                ItemCabinetQuantity.cabinet_id == uuid_to_str(cabinet_req.old_cabinet_id)
            )
        else:
            old_qty_query = old_qty_query.where(
                ItemCabinetQuantity.cabinet_id.is_(None)
            )
        
        old_qty_result = await db.execute(old_qty_query)
        old_item_qty = old_qty_result.scalar_one_or_none()
        
        if not old_item_qty:
            # 如果舊 cabinet 沒有記錄，拋出錯誤
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        
        # 4. 驗證搬移的 quantity 不能大於 old cabinet 的 item quantity
        if cabinet_req.quantity > old_item_qty.quantity:
            # 如果請求的移動數量大於舊 cabinet 的數量，拋出錯誤
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    old_item_model = await build_item_response(item, request_model.household_id, db)
    
    now_utc8 = datetime.now(UTC_PLUS_8)
    for cabinet_req in request_model.cabinets:
        # 從舊的 cabinet 移除 quantity
        # 如果 old_cabinet_id 為 None，則查詢 cabinet_id IS NULL 的記錄
        old_qty_query = select(ItemCabinetQuantity).where(
            ItemCabinetQuantity.item_id == item.id
        )
        if cabinet_req.old_cabinet_id is not None:
            old_qty_query = old_qty_query.where(
                ItemCabinetQuantity.cabinet_id == uuid_to_str(cabinet_req.old_cabinet_id)
            )
        else:
            old_qty_query = old_qty_query.where(
                ItemCabinetQuantity.cabinet_id.is_(None)
            )
        
        old_qty_result = await db.execute(old_qty_query)
        old_item_qty = old_qty_result.scalar_one_or_none()
        
        # 此時已經驗證過 old_item_qty 存在且 quantity 足夠
        if old_item_qty.quantity == cabinet_req.quantity:
            # 如果舊數量等於移動數量，刪除舊記錄
            await db.delete(old_item_qty)
        else:
            # 減少舊 cabinet 的數量
            old_item_qty.quantity -= cabinet_req.quantity
            old_item_qty.updated_at = now_utc8
        
        # 添加到新的 cabinet
        # 如果 new_cabinet_id 為 None，則查詢 cabinet_id IS NULL 的記錄
        new_qty_query = select(ItemCabinetQuantity).where(
            ItemCabinetQuantity.item_id == item.id
        )
        if cabinet_req.new_cabinet_id is not None:
            new_qty_query = new_qty_query.where(
                ItemCabinetQuantity.cabinet_id == uuid_to_str(cabinet_req.new_cabinet_id)
            )
        else:
            new_qty_query = new_qty_query.where(
                ItemCabinetQuantity.cabinet_id.is_(None)
            )
        
        new_qty_result = await db.execute(new_qty_query)
        new_item_qty = new_qty_result.scalar_one_or_none()
        
        if new_item_qty:
            # 更新現有記錄
            new_item_qty.quantity += cabinet_req.quantity
            new_item_qty.updated_at = now_utc8
        else:
            # 創建新記錄
            new_qty = ItemCabinetQuantity(
                household_id=item.household_id,
                item_id=item.id,
                cabinet_id=uuid_to_str(cabinet_req.new_cabinet_id) if cabinet_req.new_cabinet_id is not None else None,
                quantity=cabinet_req.quantity,
                created_at=now_utc8,
                updated_at=now_utc8,
            )
            db.add(new_qty)
    
    # Update updated_at to UTC+8 timezone
    item.updated_at = now_utc8
    
    await db.commit()
    new_item_model = await build_item_response(item, request_model.household_id, db)
    
    # 生成記錄（position 變化）
    await _gen_record_position(old_item_model, new_item_model, request_model, db)




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


# 返回 old 和 new 的 cabinet 資訊 (已废弃，保留用于向后兼容)
async def _update_item_cabinet(
    item: Item,
    request_model: UpdateItemNormalRequestModel,  # 注意：这个函数已经不再被使用，仅保留用于类型检查
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


async def _update_item_category_normal(
    item: Item,
    request_model: UpdateItemNormalRequestModel,
    db: AsyncSession
) -> CategoryUpdateInfo:
    old_category_id_uuid = cast(Optional[UUID], item.category_id) if item.category_id else None
    old_category_info_dict = await get_category_info(old_category_id_uuid, cast(UUID, item.household_id), db)
    old_category_info = CategoryInfo(
        category_id=old_category_info_dict.get("category_id"),
        level_name=old_category_info_dict.get("level_name")
    )
    
    # 處理 category_id 更新：如果提供空字符串或 None，則移除 category
    if request_model.category_id is not None:
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


async def _gen_record_normal(
    old_item_model: ItemResponseModel,
    new_item_model: ItemResponseModel,
    request_model: UpdateItemNormalRequestModel,
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
    
    # category_changed 檢測：使用 category_info 中的資訊
    category_changed = False
    # 檢查 category_id 是否在請求中被設置，並且值有變化
    if request_model.category_id is not None:
        category_changed = category_info.old.category_id != category_info.new.category_id
    
    has_changes = name_changed or description_changed or min_stock_alert_changed or photo_changed or category_changed
    
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
                category_name_old=category_info.old.level_name if category_changed else None,
                category_name_new="" if (category_changed and category_info.new.category_id is None) else (category_info.new.level_name if category_changed else None),
                min_stock_count_old=old_item_model.min_stock_alert if min_stock_alert_changed else None,
                min_stock_count_new=new_item_model.min_stock_alert if min_stock_alert_changed else None,
            ),
            db
        )


async def _gen_record_quantity(
    cabinet_quantity_changes: List[tuple],  # List of (cabinet_id, cabinet_name, old_quantity, new_quantity)
    request_model: UpdateItemQuantityRequestModel,
    db: AsyncSession
) -> None:
    for cabinet_id, cabinet_name, old_quantity, new_quantity in cabinet_quantity_changes:
        await create_record(
            CreateRecordRequestModel(
                household_id=request_model.household_id,
                user_name=request_model.user_name,
                operate_type=OperateType.UPDATE.value,
                entity_type=EntityType.ITEM.value,
                cabinet_name_old=cabinet_name,
                quantity_count_old=old_quantity,
                quantity_count_new=new_quantity
            ),
            db
        )


async def _gen_record_position(
    old_item_model: ItemResponseModel,
    new_item_model: ItemResponseModel,
    request_model: UpdateItemPositionRequestModel,
    db: AsyncSession
) -> None:
    # 檢測 cabinet 是否有變化（通過比較舊的 cabinet 和新的 cabinet）
    # 這裡簡化處理，只要有位置移動就記錄
    has_position_changes = False
    for cabinet_req in request_model.cabinets:
        if cabinet_req.old_cabinet_id != cabinet_req.new_cabinet_id:
            has_position_changes = True
            break
    
    if has_position_changes:
        # 獲取 cabinet 名稱用於記錄
        old_cabinet_ids = [cabinet_req.old_cabinet_id for cabinet_req in request_model.cabinets]
        new_cabinet_ids = [cabinet_req.new_cabinet_id for cabinet_req in request_model.cabinets]
        
        # 這裡可以進一步獲取 cabinet 名稱，但為了簡化，我們記錄基本信息
        await create_record(
            CreateRecordRequestModel(
                household_id=request_model.household_id,
                user_name=request_model.user_name,
                operate_type=OperateType.UPDATE.value,
                entity_type=EntityType.ITEM.value,
                # 可以添加 cabinet 相關的記錄字段，如果需要的話
            ),
            db
        )

