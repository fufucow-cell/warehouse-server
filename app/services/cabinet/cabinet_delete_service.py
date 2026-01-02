from typing import Optional, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table.cabinet import Cabinet
from app.schemas.cabinet_request import DeleteCabinetRequestModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str

# ==================== Delete ====================
async def delete_cabinet(
    request_model: DeleteCabinetRequestModel,
    db: AsyncSession
) -> None:
    cabinet_id_str = uuid_to_str(request_model.cabinet_id)
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == cabinet_id_str)
    )

    cabinet = result.scalar_one_or_none()

    if not cabinet:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)

    cabinet_name = cast(str, cabinet.name)
    household_id = cast(UUID, cabinet.household_id)
    
    await db.delete(cabinet)
    await db.commit()
    await _create_record(
        household_id=household_id,
        user_name=request_model.user_name,
        operate_type=OperateType.DELETE.value,
        cabinet_name_old=cabinet_name,
        db=db
    )


# ==================== Private Method ====================

async def _create_record(
    household_id: UUID,
    user_name: str,
    operate_type: int,
    db: AsyncSession,
    cabinet_name_old: Optional[str] = None,
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=household_id,
            user_name=user_name,
            operate_type=operate_type,
            entity_type=EntityType.CABINET.value,
            cabinet_name_old=cabinet_name_old,
        ),
        db
    )

