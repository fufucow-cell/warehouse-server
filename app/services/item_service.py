from typing import Optional, List, Dict, Set, cast, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.table import Item, Cabinet, Category
from app.schemas.item_request import CreateItemRequestModel, ReadItemRequestModel, UpdateItemRequestModel, DeleteItemRequestModel, CabinetInfo, CabinetUpdateInfo, CategoryInfo, CategoryUpdateInfo
from app.schemas.item_response import ItemResponseModel
from app.schemas.category_response import CategoryResponseModel
from app.schemas.cabinet_request import ReadCabinetRequestModel
from app.schemas.cabinet_response import CabinetResponseModel
from app.schemas.category_request import ReadCategoryRequestModel
from app.schemas.record_request import CreateRecordRequestModel
from app.services.cabinet_service import read_cabinet
from app.services.category_service import read_category
from app.services.record_service import create_record
from app.table.record import OperateType, EntityType, RecordType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_file import delete_uploaded_file, validate_base64_image, save_base64_image

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))


# ==================== Create ====================
async def create_item(
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> ItemResponseModel:
    photo_url = None

    if not request_model.name or not request_model.name.strip():
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    if request_model.quantity < 0:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    if request_model.min_stock_alert < 0:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    if request_model.photo is not None:
        if not validate_base64_image(request_model.photo):
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        photo_url = save_base64_image(request_model.photo)
        if not photo_url:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # Set created_at and updated_at to UTC+8 timezone
    now_utc8 = datetime.now(UTC_PLUS_8)
    
    new_item = Item(
        household_id=request_model.household_id,
        cabinet_id=request_model.cabinet_id,
        category_id=request_model.category_id,
        name=request_model.name,
        description=request_model.description,
        quantity=request_model.quantity,
        min_stock_alert=request_model.min_stock_alert,
        photo=photo_url,
        created_at=now_utc8,
        updated_at=now_utc8,
    )
    db.add(new_item)
    await db.flush()
    
    # 創建 record
    new_item_model = await _build_item_response(new_item, request_model.household_id, db)
    await _gen_create_record(new_item_model, request_model, db)
    
    return new_item_model


# ==================== Read ====================
async def read_item(
    request_model: ReadItemRequestModel,
    db: AsyncSession
) -> List[ItemResponseModel]:
    query = select(Item).where(Item.household_id == request_model.household_id)

    if request_model.cabinet_id is not None:
        query = query.where(Item.cabinet_id == request_model.cabinet_id)
    
    if request_model.category_ids is not None and len(request_model.category_ids) > 0:
        query = query.where(Item.category_id.in_(request_model.category_ids))
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    if not items:
        return []
    
    # 收集所有 cabinet_ids 並獲取 cabinets 資訊
    cabinet_ids: Set[UUID] = {cast(UUID, item.cabinet_id) for item in items if item.cabinet_id is not None}
    cabinets_dict = await _get_cabinets_dict(request_model.household_id, cabinet_ids, db)
    
    # 收集所有 category_ids 並獲取 categories
    category_ids: Set[UUID] = {cast(UUID, item.category_id) for item in items if item.category_id is not None}
    categories_dict = await _get_categories_dict(request_model.household_id, category_ids, db)
    
    response_models = []
    for item in items:
        cabinet_name = None
        cabinet_room_id = None
        
        if item.cabinet_id is not None and item.cabinet_id in cabinets_dict:
            cabinet_info = cabinets_dict[cast(UUID, item.cabinet_id)]
            cabinet_name = cabinet_info["cabinet"].name
            cabinet_room_id = cabinet_info["room_id"]
        
        category = None
        if item.category_id is not None and item.category_id in categories_dict:
            category = categories_dict[cast(UUID, item.category_id)]
        
        response_model = ItemResponseModel(
            id=cast(UUID, item.id),
            cabinet_id=cast(Optional[UUID], item.cabinet_id),
            cabinet_name=cabinet_name,
            cabinet_room_id=cabinet_room_id,
            category=category,
            name=cast(str, item.name),
            description=cast(Optional[str], item.description),
            quantity=cast(int, item.quantity),
            min_stock_alert=cast(int, item.min_stock_alert),
            photo=cast(Optional[str], item.photo)
        )
        response_models.append(response_model)
    
    return response_models


# ==================== Update ====================
async def update_item(
    request_model: UpdateItemRequestModel,
    db: AsyncSession
) -> ItemResponseModel:
    result = await db.execute(
        select(Item).where(
            Item.id == request_model.id,
            Item.household_id == request_model.household_id
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    old_item_model = await _build_item_response(item, request_model.household_id, db)
    
    # 處理照片更新邏輯
    _update_item_photo(item, request_model.photo)
    
    # 處理 cabinet_id 更新
    cabinet_info = await _update_item_cabinet(item, request_model, request_model.household_id, db)
    
    # 處理 category_id 更新
    category_info = await _update_item_category(item, request_model, request_model.household_id, db)
    
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
    if request_model.quantity is not None:
        if request_model.quantity < 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        item.quantity = request_model.quantity
    if request_model.min_stock_alert is not None:
        if request_model.min_stock_alert < 0:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
        item.min_stock_alert = request_model.min_stock_alert
    
    # Update updated_at to UTC+8 timezone
    item.updated_at = datetime.now(UTC_PLUS_8)
    
    await db.commit()
    new_item_model = await _build_item_response(item, request_model.household_id, db)
    await _gen_update_record(old_item_model, new_item_model, request_model, cabinet_info, category_info, db)
    return new_item_model


# ==================== Delete ====================
async def delete_item(
    request_model: DeleteItemRequestModel,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Item).where(
            Item.id == request_model.id,
            Item.household_id == request_model.household_id
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    # Build item model before deleting to get complete information
    old_item_model = await _build_item_response(item, request_model.household_id, db)
    
    if item.photo is not None:
        delete_uploaded_file(cast(str, item.photo))
    
    await db.delete(item)
    await db.commit()
    await _gen_delete_record(old_item_model, request_model, db)


# ==================== Private Method ====================

def _determine_record_type(
    quantity_count_old: Optional[int] = None,
    quantity_count_new: Optional[int] = None,
    min_stock_count_old: Optional[int] = None,
    min_stock_count_new: Optional[int] = None
) -> int:
    quantity = quantity_count_new if quantity_count_new is not None else quantity_count_old
    min_stock = min_stock_count_new if min_stock_count_new is not None else min_stock_count_old
    
    if quantity is None or min_stock is None:
        return RecordType.NORMAL.value
    
    if min_stock == 0:
        return RecordType.NORMAL.value
    
    if quantity < min_stock:
        return RecordType.WARNING.value
    
    return RecordType.NORMAL.value

async def _get_cabinets_dict(
    household_id: UUID,
    cabinet_ids: Set[UUID],
    db: AsyncSession
) -> Dict[UUID, Dict[str, Any]]:
    cabinets_dict = {}
    if cabinet_ids:
        cabinets_result = await read_cabinet(
            ReadCabinetRequestModel(
                household_id=household_id,
                cabinet_ids=list(cabinet_ids)
            ),
            db
        )
        # cabinets_result is List[CabinetResponseListModel]
        # Each CabinetResponseListModel contains a list of CabinetResponseModel
        for cabinet_list_model in cabinets_result:
            # Extract room_id from CabinetResponseListModel
            room_id = None
            if cabinet_list_model.room_id and cabinet_list_model.room_id != "":
                try:
                    room_id = UUID(cabinet_list_model.room_id)
                except (ValueError, AttributeError):
                    room_id = None
            for cabinet in cabinet_list_model.cabinet:
                cabinets_dict[cabinet.cabinet_id] = {
                    "cabinet": cabinet,
                    "room_id": room_id
                }
    return cabinets_dict


async def _get_categories_dict(
    household_id: UUID,
    category_ids: Set[UUID],
    db: AsyncSession
) -> Dict[UUID, CategoryResponseModel]:
    categories_dict = {}
    
    if category_ids:
        for category_id in category_ids:
            categories_result = await read_category(
                ReadCategoryRequestModel(
                    household_id=household_id,
                    category_id=category_id
                ),
                db
            )
            if categories_result:
                categories_dict[category_id] = categories_result[0]
    return categories_dict


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


# 獲取 cabinet 資訊（cabinet_id, cabinet_name, room_id）
async def _get_cabinet_info(
    cabinet_id: Optional[UUID],
    household_id: UUID,
    db: AsyncSession
) -> CabinetInfo:
    if cabinet_id is None:
        return CabinetInfo(
            cabinet_id=None,
            cabinet_name=None,
            room_id=None
        )
    
    cabinets_result = await read_cabinet(
        ReadCabinetRequestModel(
            household_id=household_id,
            cabinet_ids=[cabinet_id]
        ),
        db
    )
    
    cabinet_name = None
    room_id = None
    
    if cabinets_result:
        for cabinet_list_model in cabinets_result:
            if cabinet_list_model.room_id and cabinet_list_model.room_id != "":
                try:
                    room_id = UUID(cabinet_list_model.room_id)
                except (ValueError, AttributeError):
                    room_id = None
            for cabinet in cabinet_list_model.cabinet:
                cabinet_id_uuid = UUID(str(cabinet_id))

                if cabinet.cabinet_id == cabinet_id_uuid:
                    cabinet_name = cabinet.name
                    break

            if cabinet_name is not None:
                break
    
    return CabinetInfo(
        cabinet_id=cabinet_id,
        cabinet_name=cabinet_name,
        room_id=room_id
    )


# 返回 old 和 new 的 cabinet 資訊
async def _update_item_cabinet(
    item: Item,
    request_model: UpdateItemRequestModel,
    household_id: UUID,
    db: AsyncSession
) -> CabinetUpdateInfo:
    old_cabinet_info = await _get_cabinet_info(item.cabinet_id, household_id, db)
    
    # 處理 cabinet_id 更新：如果提供空字符串或 None，則移除 cabinet
    new_cabinet_id: Optional[UUID] = None
    if 'cabinet_id' in request_model.model_fields_set:
        item.cabinet_id = request_model.cabinet_id
        # 確保 cabinet_id 是正確的 UUID 類型
        if request_model.cabinet_id is not None:
            new_cabinet_id = cast(UUID, request_model.cabinet_id)
        else:
            new_cabinet_id = None
    else:
        # 如果沒有更新，使用舊的 cabinet_id
        new_cabinet_id = cast(Optional[UUID], item.cabinet_id)
    
    new_cabinet_info = await _get_cabinet_info(new_cabinet_id, household_id, db)
    
    return CabinetUpdateInfo(
        old=old_cabinet_info,
        new=new_cabinet_info
    )


# 獲取 category 資訊（category_id, category_name）
async def _get_category_info(
    category_id: Optional[UUID],
    household_id: UUID,
    db: AsyncSession
) -> CategoryInfo:
    if category_id is None:
        return CategoryInfo(
            category_id=None,
            category_name=None
        )
    
    categories_result = await read_category(
        ReadCategoryRequestModel(
            household_id=household_id,
            category_id=category_id
        ),
        db
    )
    
    category_name = None
    if categories_result:
        category_name = categories_result[0].name
    
    return CategoryInfo(
        category_id=category_id,
        category_name=category_name
    )


# 處理 category_id 更新邏輯
# 如果字段在 model_fields_set 中，則更新對應的值（可以是 None 或 UUID）
# 返回 old 和 new 的 category 資訊
async def _update_item_category(
    item: Item,
    request_model: UpdateItemRequestModel,
    household_id: UUID,
    db: AsyncSession
) -> CategoryUpdateInfo:
    # 獲取更新前的 category 資訊
    old_category_info = await _get_category_info(item.category_id, household_id, db)
    
    # 處理 category_id 更新：如果提供空字符串或 None，則移除 category
    if 'category_id' in request_model.model_fields_set:
        item.category_id = request_model.category_id
    
    # 獲取更新後的 category 資訊
    new_category_info = await _get_category_info(item.category_id, household_id, db)
    
    return CategoryUpdateInfo(
        old=old_category_info,
        new=new_category_info
    )


async def _build_item_response(
    item: Item,
    household_id: UUID,
    db: AsyncSession
) -> ItemResponseModel:
    cabinet_name = None
    cabinet_room_id = None
    category = None
    
    if item.cabinet_id is not None:
        cabinets_result = await read_cabinet(
            ReadCabinetRequestModel(
                household_id=household_id,
                cabinet_ids=[cast(UUID, item.cabinet_id)]
            ),
            db
        )
        # cabinets_result is List[CabinetResponseListModel]
        # Each CabinetResponseListModel contains a list of CabinetResponseModel
        if cabinets_result:
            for cabinet_list_model in cabinets_result:
                # Extract room_id from CabinetResponseListModel
                room_id = None
                if cabinet_list_model.room_id and cabinet_list_model.room_id != "":
                    try:
                        room_id = UUID(cabinet_list_model.room_id)
                    except (ValueError, AttributeError):
                        room_id = None
                for cabinet in cabinet_list_model.cabinet:
                    if cabinet.cabinet_id == item.cabinet_id:
                        cabinet_name = cabinet.name
                        cabinet_room_id = room_id
                        break
                if cabinet_name is not None:
                    break
    
    if item.category_id is not None:
        categories_result = await read_category(
            ReadCategoryRequestModel(
                household_id=household_id,
                category_id=cast(UUID, item.category_id)
            ),
            db
        )
        if categories_result:
            category = categories_result[0]
    
    return ItemResponseModel(
        id=cast(UUID, item.id),
        cabinet_id=cast(Optional[UUID], item.cabinet_id),
        cabinet_name=cabinet_name,
        cabinet_room_id=cabinet_room_id,
        category=category,
        name=cast(str, item.name),
        description=cast(Optional[str], item.description),
        quantity=cast(int, item.quantity),
        min_stock_alert=cast(int, item.min_stock_alert),
        photo=cast(Optional[str], item.photo)
    )


async def _gen_create_record(
    item_model: ItemResponseModel,
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> None:
    record_type = _determine_record_type(
        quantity_count_new=item_model.quantity,
        min_stock_count_new=item_model.min_stock_alert
    )
    
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.CREATE.value,
            entity_type=EntityType.ITEM.value,
            record_type=record_type,
            item_name_new=item_model.name,
            item_description_new=item_model.description,
            item_photo_new=item_model.photo,
            cabinet_name_new=item_model.cabinet_name,
            category_name_new=item_model.category.name if item_model.category else None,
            quantity_count_new=item_model.quantity,
            min_stock_count_new=item_model.min_stock_alert,
        ),
        db
    )


async def _gen_update_record(
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
        record_type = RecordType.NORMAL.value
        if quantity_changed or min_stock_alert_changed:
            record_type = _determine_record_type(
                quantity_count_old=old_item_model.quantity,
                quantity_count_new=new_item_model.quantity if quantity_changed else None,
                min_stock_count_old=old_item_model.min_stock_alert,
                min_stock_count_new=new_item_model.min_stock_alert if min_stock_alert_changed else None
            )
        
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
                record_type=record_type,
                item_name_old=old_item_model.name if name_changed else None,
                item_name_new=new_item_model.name if name_changed else None,
                item_description_old=old_item_model.description if description_changed else None,
                item_description_new=get_new_value(request_model.description, new_item_model.description, description_changed),
                item_photo_old=old_item_model.photo if photo_changed else None,
                item_photo_new=get_new_value(request_model.photo, new_item_model.photo, photo_changed),
                cabinet_name_old=cabinet_info.old.cabinet_name if cabinet_changed else None,
                cabinet_name_new="" if (cabinet_changed and cabinet_info.new.cabinet_id is None) else (cabinet_info.new.cabinet_name if cabinet_changed else None),
                category_name_old=category_info.old.category_name if category_changed else None,
                category_name_new="" if (category_changed and category_info.new.category_id is None) else (category_info.new.category_name if category_changed else None),
                quantity_count_old=old_item_model.quantity if quantity_changed else None,
                quantity_count_new=new_item_model.quantity if quantity_changed else None,
                min_stock_count_old=old_item_model.min_stock_alert if min_stock_alert_changed else None,
                min_stock_count_new=new_item_model.min_stock_alert if min_stock_alert_changed else None,
            ),
            db
        )


async def _gen_delete_record(
    item_model: ItemResponseModel,
    request_model: DeleteItemRequestModel,
    db: AsyncSession
) -> None:
    record_type = _determine_record_type(
        quantity_count_old=item_model.quantity,
        min_stock_count_old=item_model.min_stock_alert
    )
    
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.DELETE.value,
            entity_type=EntityType.ITEM.value,
            record_type=record_type,
            item_name_old=item_model.name,
            item_description_old=item_model.description,
            item_photo_old=item_model.photo,
            cabinet_name_old=item_model.cabinet_name,
            category_name_old=item_model.category.name if item_model.category else None,
            quantity_count_old=item_model.quantity,
            min_stock_count_old=item_model.min_stock_alert,
        ),
        db
    )