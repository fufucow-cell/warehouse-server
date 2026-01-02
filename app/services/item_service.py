from typing import Optional, List, Dict, Set, cast, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from app.table.category import Category
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from app.table import Item, ItemCabinetQuantity
from app.schemas.item_request import CreateItemRequestModel, ReadItemRequestModel, UpdateItemRequestModel, DeleteItemRequestModel, CabinetInfo, CabinetUpdateInfo, CategoryInfo, CategoryUpdateInfo
from app.schemas.item_response import ItemInCabinetInfo, ItemResponseModel
from app.schemas.category_response import CategoryResponseModel
from app.schemas.cabinet_request import ReadCabinetRequestModel
from app.schemas.category_request import ReadCategoryRequestModel
from app.schemas.record_request import CreateRecordRequestModel
from app.services.cabinet.cabinet_read_service import read_cabinet
from app.services.category.category_read_service import build_category_tree, gen_single_category_tree, read_category, get_level_names
from app.services.record_service import create_record
from app.table.record import OperateType, EntityType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_file import delete_uploaded_file, validate_base64_image, save_base64_image
from app.utils.util_uuid import uuid_to_str

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
    
    # 創建 item（不再包含 cabinet_id，通過 item_cabinet_quantity 表維護）
    new_item = Item(
        household_id=uuid_to_str(request_model.household_id),
        category_id=uuid_to_str(request_model.category_id),
        name=request_model.name,
        description=request_model.description,
        min_stock_alert=request_model.min_stock_alert,
        photo=photo_url,
        created_at=now_utc8,
        updated_at=now_utc8,
    )
    db.add(new_item)
    await db.flush()
    
    # 如果有 cabinet_id 和 quantity，創建 item_cabinet_quantity 記錄
    if request_model.cabinet_id is not None and request_model.quantity > 0:
        item_cabinet_qty = ItemCabinetQuantity(
            household_id=uuid_to_str(request_model.household_id),
            item_id=new_item.id,
            cabinet_id=uuid_to_str(request_model.cabinet_id),
            quantity=request_model.quantity,
            created_at=now_utc8,
            updated_at=now_utc8,
        )
        db.add(item_cabinet_qty)
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
    query = select(Item).where(Item.household_id == uuid_to_str(request_model.household_id))
    
    if request_model.category_ids is not None and len(request_model.category_ids) > 0:
        query = query.where(Item.category_id.in_(request_model.category_ids))
    
    # 如果指定了 cabinet_id，通過 item_cabinet_quantity 表來篩選 items
    if request_model.cabinet_id is not None:
        cabinet_id_str = uuid_to_str(request_model.cabinet_id)
        # 查詢該 cabinet 下的所有 item_ids
        item_quantities_query = select(ItemCabinetQuantity.item_id).where(
            ItemCabinetQuantity.cabinet_id == cabinet_id_str
        )
        item_quantities_result = await db.execute(item_quantities_query)
        cabinet_item_ids = {row[0] for row in item_quantities_result.all()}
        
        if cabinet_item_ids:
            query = query.where(Item.id.in_(cabinet_item_ids))
        else:
            # 如果該 cabinet 下沒有任何 items，返回空列表
            return []
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    if not items:
        return []
    
    # 收集所有 cabinet_ids（從 item_cabinet_quantity 表中獲取）
    item_ids = {item.id for item in items}
    cabinet_quantities_query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.item_id.in_(item_ids)
    )
    cabinet_quantities_result = await db.execute(cabinet_quantities_query)
    cabinet_quantities = cabinet_quantities_result.scalars().all()
    
    cabinet_ids: Set[UUID] = {cast(UUID, qty.cabinet_id) for qty in cabinet_quantities}
    cabinets_dict = await _get_cabinets_dict(request_model.household_id, cabinet_ids, db)
    
    # 收集所有 category_ids 並獲取 categories
    category_ids: Set[UUID] = {cast(UUID, item.category_id) for item in items if item.category_id is not None}
    categories_dict = await _get_categories_dict(request_model.household_id, category_ids, db)
    
    # 收集所有 item_ids 並獲取 quantities
    item_ids_set = {item.id for item in items}
    quantities_dict = await _get_item_quantities_dict(item_ids_set, request_model.cabinet_id, db)
    
    # 構建 item 到 cabinet 的映射（從 item_cabinet_quantity 表）
    item_to_cabinet_map: Dict[str, UUID] = {}
    for qty in cabinet_quantities:
        # 如果指定了 cabinet_id，只使用該 cabinet；否則使用第一個找到的 cabinet
        if request_model.cabinet_id is not None:
            if qty.cabinet_id == uuid_to_str(request_model.cabinet_id):
                if qty.item_id not in item_to_cabinet_map:
                    item_to_cabinet_map[qty.item_id] = cast(UUID, qty.cabinet_id)
        else:
            # 如果沒有指定 cabinet_id，使用第一個找到的 cabinet
            if qty.item_id not in item_to_cabinet_map:
                item_to_cabinet_map[qty.item_id] = cast(UUID, qty.cabinet_id)
    
    response_models = []
    for item in items:
        cabinet_id = item_to_cabinet_map.get(item.id)
        cabinet_name = None
        cabinet_room_id = None
        
        if cabinet_id is not None and cabinet_id in cabinets_dict:
            cabinet_info = cabinets_dict[cabinet_id]
            cabinet_name = cabinet_info["cabinet"].name
            cabinet_room_id = cabinet_info["room_id"]
        
        category = None
        if item.category_id is not None and item.category_id in categories_dict:
            category = categories_dict[cast(UUID, item.category_id)]
        
        # 從 item_cabinet_quantity 表獲取 quantity
        quantity = quantities_dict.get(item.id, 0)
        
        response_model = ItemResponseModel(
            id=cast(UUID, item.id),
            cabinet_id=cabinet_id,
            cabinet_name=cabinet_name,
            cabinet_room_id=cabinet_room_id,
            category=category,
            name=cast(str, item.name),
            description=cast(Optional[str], item.description),
            quantity=quantity,
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
            Item.id == uuid_to_str(request_model.id),
            Item.household_id == uuid_to_str(request_model.household_id)
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    old_item_model = await _build_item_response(item, request_model.household_id, db)
    
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
            Item.id == uuid_to_str(request_model.id),
            Item.household_id == uuid_to_str(request_model.household_id)
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

# ==================== Public Method ====================

# 生成 item 的 category tree
async def gen_item_with_category_tree(
    item: Item,
    categories: List[Category],
) -> ItemInCabinetInfo:
    category = gen_single_category_tree(categories, item.category_id)
    
    return ItemInCabinetInfo(
        item_id=cast(UUID, item.id),
        name=cast(str, item.name),
        description=cast(Optional[str], item.description),
        quantity=0,
        min_stock_alert=cast(int, item.min_stock_alert),
        photo=cast(Optional[str], item.photo),
        category=category
    )


# ==================== Private Method ====================

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
async def _get_item_quantities_dict(
    item_ids: Set[str],
    cabinet_id: Optional[UUID],
    db: AsyncSession
) -> Dict[str, int]:
    quantities_dict: Dict[str, int] = {}
    
    if not item_ids:
        return quantities_dict
    
    query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.item_id.in_(item_ids)
    )
    
    # 如果指定了 cabinet_id，只查詢該 cabinet 的 quantity
    if cabinet_id is not None:
        query = query.where(ItemCabinetQuantity.cabinet_id == uuid_to_str(cabinet_id))
    
    result = await db.execute(query)
    quantities = result.scalars().all()
    
    for qty in quantities:
        item_id = qty.item_id
        if item_id in quantities_dict:
            quantities_dict[item_id] += qty.quantity
        else:
            quantities_dict[item_id] = qty.quantity
    
    return quantities_dict


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
    old_cabinet_info = await _get_cabinet_info(old_cabinet_id_uuid, old_household_id_uuid, db)
    
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
    new_cabinet_info = await _get_cabinet_info(new_cabinet_id, household_id_uuid, db)
    
    return CabinetUpdateInfo(
        old=old_cabinet_info,
        new=new_cabinet_info
    )


async def _get_category_info(
    category_id: Optional[UUID],
    db: AsyncSession
) -> CategoryInfo:
    if category_id is None:
        return CategoryInfo(
            category_id=None,
            level_name=None
        )
    
    level_names = await get_level_names(
        category_id=category_id,
        db=db
    )
    level_name = ";".join(level_names) if level_names else None
    return CategoryInfo(
        category_id=category_id,
        level_name=level_name
    )


async def _update_item_category(
    item: Item,
    request_model: UpdateItemRequestModel,
    db: AsyncSession
) -> CategoryUpdateInfo:
    old_category_id_uuid = cast(Optional[UUID], item.category_id) if item.category_id else None
    old_category_info = await _get_category_info(old_category_id_uuid, db)
    
    # 處理 category_id 更新：如果提供空字符串或 None，則移除 category
    if 'category_id' in request_model.model_fields_set:
        item.category_id = uuid_to_str(request_model.category_id)
    
    new_category_id_uuid = cast(Optional[UUID], item.category_id) if item.category_id else None
    new_category_info = await _get_category_info(new_category_id_uuid, db)
    return CategoryUpdateInfo(
        old=old_category_info,
        new=new_category_info
    )


async def _build_item_response(
    item: Item,
    household_id: UUID,
    db: AsyncSession,
    cabinet_id: Optional[UUID] = None
) -> ItemResponseModel:
    cabinet_name = None
    cabinet_room_id = None
    category = None
    
    # 從 item_cabinet_quantity 表獲取 cabinet_id（使用指定的 cabinet_id 或第一個找到的）
    cabinet_id_for_lookup = cabinet_id
    if cabinet_id_for_lookup is None:
        # 如果沒有指定，獲取第一個找到的 cabinet_id
        cabinet_qty_query = select(ItemCabinetQuantity).where(
            ItemCabinetQuantity.item_id == item.id
        ).limit(1)
        cabinet_qty_result = await db.execute(cabinet_qty_query)
        cabinet_qty = cabinet_qty_result.scalar_one_or_none()
        if cabinet_qty:
            cabinet_id_for_lookup = cast(UUID, cabinet_qty.cabinet_id)
    
    if cabinet_id_for_lookup is not None:
        cabinets_result = await read_cabinet(
            ReadCabinetRequestModel(
                household_id=household_id,
                cabinet_ids=[cabinet_id_for_lookup]
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
                    if cabinet.cabinet_id == cabinet_id_for_lookup:
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
    
    # 從 item_cabinet_quantity 表獲取 quantity
    quantity = 0
    if item.id:
        quantities_dict = await _get_item_quantities_dict({item.id}, cabinet_id_for_lookup, db)
        quantity = quantities_dict.get(item.id, 0)
    
    return ItemResponseModel(
        id=cast(UUID, item.id),
        cabinet_id=cabinet_id_for_lookup,
        cabinet_name=cabinet_name,
        cabinet_room_id=cabinet_room_id,
        category=category,
        name=cast(str, item.name),
        description=cast(Optional[str], item.description),
        quantity=quantity,
        min_stock_alert=cast(int, item.min_stock_alert),
        photo=cast(Optional[str], item.photo)
    )


async def _gen_create_record(
    item_model: ItemResponseModel,
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.CREATE.value,
            entity_type=EntityType.ITEM.value,
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


async def _gen_delete_record(
    item_model: ItemResponseModel,
    request_model: DeleteItemRequestModel,
    db: AsyncSession
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.DELETE.value,
            entity_type=EntityType.ITEM.value,
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