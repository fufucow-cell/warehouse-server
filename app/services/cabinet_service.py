from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.table.cabinet import Cabinet
from app.table.item import Item
from app.schemas.cabinet_request import CreateCabinetRequestModel, ReadCabinetRequestModel, UpdateCabinetRequestModel, DeleteCabinetRequestModel
from app.schemas.cabinet_response import CabinetResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType, RecordType
from app.services.record_service import create_record
from app.utils.util_error_map import ServerErrorCode

# ==================== Create ====================
async def create_cabinet(
    request_model: CreateCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetResponseModel]:
    new_cabinet = Cabinet(
        household_id=request_model.household_id,
        room_id=request_model.room_id,
        name=request_model.name,
    )
    db.add(new_cabinet)
    await db.commit()
    
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.CREATE.value,
            entity_type=EntityType.CABINET.value,
            record_type=RecordType.NORMAL.value,
            cabinet_name_new=new_cabinet.name,
        ),
        db
    )
    
    return await read_cabinet(
        ReadCabinetRequestModel(household_id=request_model.household_id),
        db
    )

# ==================== Read ====================
async def read_cabinet(
    request_model: ReadCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetResponseModel]:
    query = select(Cabinet).where(Cabinet.household_id == request_model.household_id)
    
    if request_model.room_id is not None:
        query = query.where(Cabinet.room_id == request_model.room_id)
    
    if request_model.cabinet_ids is not None and len(request_model.cabinet_ids) > 0:
        query = query.where(Cabinet.id.in_(request_model.cabinet_ids))
    
    result = await db.execute(query)
    cabinets = result.scalars().all()

    if not cabinets:
        return []
    
    response_models = []
    
    for cabinet in cabinets:
        item_count_result = await db.execute(
            select(func.count(Item.id)).where(Item.cabinet_id == cabinet.id)
        )
        item_count = item_count_result.scalar() or 0
        model = CabinetResponseModel(
            cabinet_id=cabinet.id,
            room_id=cabinet.room_id,
            name=cabinet.name,
            item_count=item_count
        )
        response_models.append(model)
    
    return response_models

# ==================== Update ====================
async def update_cabinet(
    request_model: UpdateCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetResponseModel]:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == request_model.cabinet_id)
    )
    cabinet = result.scalar_one_or_none()
    
    if not cabinet:
        raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_41
    
    old_cabinet_name = cabinet.name
    old_room_name = cabinet.room_name
    old_room_id = cabinet.room_id
    isRoomChanged = False
    isCabinetNameChanged = False
    
    if request_model.room_id is not None and old_room_id != request_model.room_id:
        cabinet.room_id = request_model.room_id
        isRoomChanged = True

    if request_model.name is not None and old_cabinet_name != request_model.name:
        if not request_model.name.strip():
            raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_41

        cabinet.name = request_model.name
        isCabinetNameChanged = True
    
    await db.commit()
    
    if isCabinetNameChanged or isRoomChanged:
        await create_record(
            CreateRecordRequestModel(
                household_id=cabinet.household_id,
                user_name=request_model.user_name,
                operate_type=OperateType.UPDATE.value,
                entity_type=EntityType.CABINET.value,
                record_type=RecordType.NORMAL.value,
                cabinet_name_old=old_cabinet_name if isCabinetNameChanged else None,
                cabinet_name_new=request_model.name if isCabinetNameChanged else None,
                room_name_old=old_room_name if isRoomChanged else None,
                room_name_new=request_model.room_name if isRoomChanged else None,
            ),
            db
        )
    
    return await read_cabinet(
        ReadCabinetRequestModel(household_id=cabinet.household_id),
        db
    )


# ==================== Delete ====================
async def delete_cabinet(
    request_model: DeleteCabinetRequestModel,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == request_model.cabinet_id)
    )

    cabinet = result.scalar_one_or_none()

    if not cabinet:
        raise ServerErrorCode.REQUEST_PARAMETERS_INVALID_41

    cabinet_name = cabinet.name
    household_id = cabinet.household_id
    
    await db.delete(cabinet)
    await db.commit()
    await create_record(
        CreateRecordRequestModel(
            household_id=household_id,
            user_name=request_model.user_name,
            operate_type=OperateType.DELETE.value,
            entity_type=EntityType.CABINET.value,
            record_type=RecordType.NORMAL.value,
            cabinet_name_old=cabinet_name,
        ),
        db
    )