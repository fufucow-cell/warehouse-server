from typing import Optional, List, Dict, Set
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.table import Item, Cabinet, Category
from app.schemas.item_request import CreateItemRequestModel, ReadItemRequestModel, UpdateItemRequestModel, DeleteItemRequestModel
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
from app.utils.util_file import delete_uploaded_file, validate_base64_image, save_base64_image


# ==================== Create ====================
async def create_item(
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> None:
    photo_url = None

    if not request_model.name or not request_model.name.strip():
        raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
    if request_model.quantity < 0:
        raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
    if request_model.min_stock_alert < 0:
        raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
    if request_model.photo is not None:
        if not validate_base64_image(request_model.photo):
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
        photo_url = save_base64_image(request_model.photo)
        if not photo_url:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
    
    new_item = Item(
        household_id=request_model.household_id,
        room_id=request_model.room_id,
        cabinet_id=request_model.cabinet_id,
        category_id=request_model.category_id,
        name=request_model.name,
        description=request_model.description,
        quantity=request_model.quantity,
        min_stock_alert=request_model.min_stock_alert,
        photo=photo_url
    )
    db.add(new_item)
    await db.commit()
    
    # 創建 record
    new_item_model = await _build_item_response(new_item, request_model.household_id, db)
    await _gen_create_record(new_item_model, request_model, db)


# ==================== Read ====================
async def read_item(
    request_model: ReadItemRequestModel,
    db: AsyncSession
) -> List[ItemResponseModel]:
    query = select(Item).where(Item.household_id == request_model.household_id)

    if request_model.room_id is not None:
        query = query.where(Item.room_id == request_model.room_id)
    
    if request_model.cabinet_id is not None:
        query = query.where(Item.cabinet_id == request_model.cabinet_id)
    
    if request_model.category_ids is not None and len(request_model.category_ids) > 0:
        query = query.where(Item.category_id.in_(request_model.category_ids))
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    if not items:
        return []
    
    # 收集所有 cabinet_ids 並獲取 cabinets 資訊
    cabinet_ids = {item.cabinet_id for item in items if item.cabinet_id}
    cabinets_dict = await _get_cabinets_dict(request_model.household_id, cabinet_ids, db)
    
    # 收集所有 category_ids 並獲取 categories
    category_ids = {item.category_id for item in items if item.category_id}
    categories_dict = await _get_categories_dict(request_model.household_id, category_ids, db)
    
    response_models = []
    for item in items:
        cabinet_name = None
        
        if item.cabinet_id and item.cabinet_id in cabinets_dict:
            cabinet_name = cabinets_dict[item.cabinet_id].name
        
        category = None
        if item.category_id and item.category_id in categories_dict:
            category = categories_dict[item.category_id]
        
        response_model = ItemResponseModel(
            id=item.id,
            room_id=item.room_id,
            room_name=None,
            cabinet_id=item.cabinet_id,
            cabinet_name=cabinet_name,
            category=category,
            name=item.name,
            description=item.description,
            quantity=item.quantity,
            min_stock_alert=item.min_stock_alert,
            photo=item.photo
        )
        response_models.append(response_model)
    
    return response_models


# ==================== Update ====================
async def update_item(
    request_model: UpdateItemRequestModel,
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
        raise ServerErrorCode.REQUEST_PATH_INVALID_42
    
    old_item_model = await _build_item_response(item, request_model.household_id, db)
    
    # 處理照片更新邏輯
    _update_item_photo(item, request_model.photo)
    
    if request_model.room_id is not None:
        item.room_id = request_model.room_id
    if request_model.cabinet_id is not None:
        item.cabinet_id = request_model.cabinet_id
    if request_model.category_id is not None:
        item.category_id = request_model.category_id
    if request_model.name is not None:
        trimmed_name = request_model.name.strip()
        if len(trimmed_name) == 0:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42

        item.name = trimmed_name
    if request_model.description is not None:
        item.description = request_model.description
    if request_model.quantity is not None:
        if request_model.quantity < 0:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
        item.quantity = request_model.quantity
    if request_model.min_stock_alert is not None:
        if request_model.min_stock_alert < 0:
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
        item.min_stock_alert = request_model.min_stock_alert
    
    await db.commit()
    new_item_model = await _build_item_response(item, request_model.household_id, db)
    await _gen_update_record(old_item_model, new_item_model, request_model, db)


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
        raise ServerErrorCode.REQUEST_PATH_INVALID_42
    
    if item.photo:
        delete_uploaded_file(item.photo)
    
    await db.delete(item)
    await db.commit()
    await _gen_delete_record(item, request_model, db)


# ==================== Private Method ====================

async def _get_cabinets_dict(
    household_id: UUID,
    cabinet_ids: Set[UUID],
    db: AsyncSession
) -> Dict[UUID, CabinetResponseModel]:
    cabinets_dict = {}
    if cabinet_ids:
        cabinets_result = await read_cabinet(
            ReadCabinetRequestModel(
                household_id=household_id,
                cabinet_ids=list(cabinet_ids)
            ),
            db
        )
        cabinets_dict = {cabinet.cabinet_id: cabinet for cabinet in cabinets_result}
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
        if item.photo:
            delete_uploaded_file(item.photo)

        if photo == "":
            item.photo = None
        else:
            if not validate_base64_image(photo):
                raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
            
            photo_url = save_base64_image(photo)

            if not photo_url:
                raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_42
            
            item.photo = photo_url


async def _build_item_response(
    item: Item,
    household_id: UUID,
    db: AsyncSession
) -> ItemResponseModel:
    cabinet_name = None
    category = None
    
    if item.cabinet_id:
        cabinets_result = await read_cabinet(
            ReadCabinetRequestModel(
                household_id=household_id,
                cabinet_ids=[item.cabinet_id]
            ),
            db
        )
        if cabinets_result:
            cabinet_name = cabinets_result[0].name
    
    if item.category_id:
        categories_result = await read_category(
            ReadCategoryRequestModel(
                household_id=household_id,
                category_id=item.category_id
            ),
            db
        )
        if categories_result:
            category = categories_result[0]
    
    return ItemResponseModel(
        id=item.id,
        room_id=item.room_id,
        room_name=None,  # room_name 需要從外部服務獲取
        cabinet_id=item.cabinet_id,
        cabinet_name=cabinet_name,
        category=category,
        name=item.name,
        description=item.description,
        quantity=item.quantity,
        min_stock_alert=item.min_stock_alert,
        photo=item.photo
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
            record_type=RecordType.NORMAL.value,
            item_name_new=item_model.name,
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
    db: AsyncSession
) -> None:
    # 檢測哪些字段有變化
    name_changed = request_model.name is not None and request_model.name.strip() != old_item_model.name
    description_changed = request_model.description is not None and request_model.description != old_item_model.description
    quantity_changed = request_model.quantity is not None and request_model.quantity != old_item_model.quantity
    min_stock_alert_changed = request_model.min_stock_alert is not None and request_model.min_stock_alert != old_item_model.min_stock_alert
    photo_changed = request_model.photo is not None
    cabinet_changed = request_model.cabinet_id is not None and request_model.cabinet_id != old_item_model.cabinet_id
    category_changed = request_model.category_id is not None and request_model.category_id != old_item_model.category_id
    has_changes = name_changed or description_changed or quantity_changed or min_stock_alert_changed or photo_changed or cabinet_changed or category_changed
    
    if has_changes:
        await create_record(
            CreateRecordRequestModel(
                household_id=request_model.household_id,
                user_name=request_model.user_name,
                operate_type=OperateType.UPDATE.value,
                entity_type=EntityType.ITEM.value,
                record_type=RecordType.NORMAL.value,
                item_name_old=old_item_model.name if name_changed else None,
                item_name_new=new_item_model.name if name_changed else None,
                cabinet_name_old=old_item_model.cabinet_name if cabinet_changed else None,
                cabinet_name_new=new_item_model.cabinet_name if cabinet_changed else None,
                category_name_old=old_item_model.category.name if (category_changed and old_item_model.category) else None,
                category_name_new=new_item_model.category.name if (category_changed and new_item_model.category) else None,
                quantity_count_old=old_item_model.quantity if quantity_changed else None,
                quantity_count_new=new_item_model.quantity if quantity_changed else None,
                min_stock_count_old=old_item_model.min_stock_alert if min_stock_alert_changed else None,
                min_stock_count_new=new_item_model.min_stock_alert if min_stock_alert_changed else None,
            ),
            db
        )


async def _gen_delete_record(
    item: Item,
    request_model: DeleteItemRequestModel,
    db: AsyncSession
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.DELETE.value,
            entity_type=EntityType.ITEM.value,
            record_type=RecordType.NORMAL.value,
            item_name_old=item.name,
        ),
        db
    )