from typing import Optional, List, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table.cabinet import Cabinet
from app.schemas.cabinet_request import UpdateCabinetRequestModel
from app.schemas.cabinet_response import CabinetInRoomResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.services.cabinet.cabinet_read_service import read_cabinet_by_room
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str
from app.schemas.cabinet_request import ReadCabinetByRoomRequestModel

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Update ====================
async def update_cabinet(
    request_model: UpdateCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetInRoomResponseModel]:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == uuid_to_str(request_model.cabinet_id))
    )
    cabinet = result.scalar_one_or_none()
    
    if not cabinet:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)
    
    old_cabinet_name = cast(str, cabinet.name)
    old_room_id = cast(Optional[UUID], cabinet.room_id)
    isRoomChanged = False
    isCabinetNameChanged = False
    
    if request_model.room_id is not None and old_room_id != request_model.room_id:
        cabinet.room_id = uuid_to_str(request_model.room_id)
        isRoomChanged = True

    if request_model.name is not None and old_cabinet_name != request_model.name:
        if not request_model.name.strip():
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)

        cabinet.name = request_model.name
        isCabinetNameChanged = True
    
    # Update updated_at to UTC+8 timezone
    if isCabinetNameChanged or isRoomChanged:
        cabinet.updated_at = datetime.now(UTC_PLUS_8)
    
    await db.commit()
    
    if isCabinetNameChanged or isRoomChanged:
        await _create_record(
            household_id=cast(UUID, cabinet.household_id),
            user_name=request_model.user_name,
            operate_type=OperateType.UPDATE.value,
            cabinet_name_old=old_cabinet_name if isCabinetNameChanged else None,
            cabinet_name_new=request_model.name if isCabinetNameChanged else None,
            room_name_new=request_model.room_name if isRoomChanged else None,
            db=db
        )
    
    return await read_cabinet_by_room(
        ReadCabinetByRoomRequestModel(household_id=cast(UUID, cabinet.household_id)),
        db
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

