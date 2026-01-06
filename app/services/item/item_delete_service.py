from typing import cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table import Item
from app.schemas.item_request import DeleteItemRequestModel
from app.schemas.item_response import ItemResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.services.item.item_read_service import build_item_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_file import delete_uploaded_file
from app.utils.util_uuid import uuid_to_str

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
    old_item_model = await build_item_response(item, request_model.household_id, db)
    
    if item.photo is not None:
        delete_uploaded_file(cast(str, item.photo))
    
    await db.delete(item)
    await db.commit()
    await _gen_record(old_item_model, request_model, db)


# ==================== Private Method ====================

async def _gen_record(
    item_model: ItemResponseModel,
    request_model: DeleteItemRequestModel,
    db: AsyncSession
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            item_id=item_model.id,
            user_name=request_model.user_name,
            operate_type=OperateType.DELETE.value,
            entity_type=EntityType.ITEM_NORMAL.value,
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

