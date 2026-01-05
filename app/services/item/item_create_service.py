from typing import cast, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.table import Item, ItemCabinetQuantity
from app.schemas.item_request import CreateItemRequestModel
from app.schemas.item_response import ItemResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_file import validate_base64_image, save_base64_image
from app.utils.util_uuid import uuid_to_str

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Create ====================
async def create_item(
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> ItemResponseModel:
    photo_url = None

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
        category_id=uuid_to_str(request_model.category_id) if request_model.category_id is not None else None,
        name=request_model.name,
        description=request_model.description,
        min_stock_alert=request_model.min_stock_alert,
        photo=photo_url,
        created_at=now_utc8,
        updated_at=now_utc8,
    )
    db.add(new_item)
    await db.flush()
    
    # 總是創建 item_cabinet_quantity 記錄，cabinet_id 可以為 null，quantity 沒有值就自動補 0
    quantity = request_model.quantity if request_model.quantity > 0 else 0
    cabinet_id = uuid_to_str(request_model.cabinet_id) if request_model.cabinet_id is not None else None
    item_cabinet_qty = ItemCabinetQuantity(
            household_id=uuid_to_str(request_model.household_id),
            item_id=new_item.id,
            cabinet_id=cabinet_id,
            quantity=quantity,
            created_at=now_utc8,
            updated_at=now_utc8,
        )
    db.add(item_cabinet_qty)
    await db.flush()
        
    # 創建 record
    new_item_model = _build_item_response(
        item=new_item,
        cabinet_id=request_model.cabinet_id,
        quantity=quantity
    )
    await _gen_record(new_item_model, request_model, db)
    return new_item_model


# ==================== Private Method ====================

async def _gen_record(
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
    
def _build_item_response(
    item: Item,
    cabinet_id: Optional[UUID] = None,
    quantity: int = 0
) -> ItemResponseModel:
    return ItemResponseModel(
        id=cast(UUID, item.id),
        cabinet_id=cabinet_id,
        cabinet_name=None,
        cabinet_room_id=None,
        category=None,
        name=cast(str, item.name),
        description=cast(Optional[str], item.description),
        quantity=quantity,
        min_stock_alert=cast(int, item.min_stock_alert),
        photo=cast(Optional[str], item.photo)
    )
