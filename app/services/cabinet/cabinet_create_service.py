from typing import Optional, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.table.cabinet import Cabinet
from app.schemas.cabinet_request import CreateCabinetRequestModel
from app.schemas.cabinet_response import CabinetResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.utils.util_uuid import uuid_to_str

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Create ====================
async def create_cabinet(
    request_model: CreateCabinetRequestModel,
    db: AsyncSession
) -> CabinetResponseModel:
    now_utc8 = datetime.now(UTC_PLUS_8)
    
    new_cabinet = Cabinet(
        household_id=uuid_to_str(request_model.household_id),
        room_id=uuid_to_str(request_model.room_id),
        name=request_model.name,
        created_at=now_utc8,
        updated_at=now_utc8,
    )
    db.add(new_cabinet)
    await db.commit()
    
    await _create_record(
        household_id=request_model.household_id,
        user_name=request_model.user_name,
        operate_type=OperateType.CREATE.value,
        cabinet_name_new=request_model.name,
        db=db
    )
    
    return CabinetResponseModel(
        cabinet_id=cast(UUID, new_cabinet.id),
        room_id=cast(Optional[UUID], new_cabinet.room_id),
        name=cast(str, new_cabinet.name),
        item_quantity=0,
        items=[]
    )

# ==================== Private Method ====================

async def _create_record(
    household_id: UUID,
    user_name: str,
    operate_type: int,
    db: AsyncSession,
    cabinet_name_old: Optional[str] = None,
    cabinet_name_new: Optional[str] = None,
    room_name_new: Optional[str] = None,
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=household_id,
            user_name=user_name,
            operate_type=operate_type,
            entity_type=EntityType.CABINET.value,
            cabinet_name_old=cabinet_name_old,
            cabinet_name_new=cabinet_name_new,
            room_name_new=room_name_new,
        ),
        db
    )