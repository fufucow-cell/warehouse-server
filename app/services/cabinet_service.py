from typing import Optional, List, Dict, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.table.cabinet import Cabinet
from app.table.item import Item
from app.schemas.cabinet_request import CreateCabinetRequestModel, ReadCabinetRequestModel, UpdateCabinetRequestModel, DeleteCabinetRequestModel
from app.schemas.cabinet_response import CabinetResponseModel, CabinetResponseListModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType, RecordType
from app.services.record_service import create_record
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Create ====================
async def create_cabinet(
    request_model: CreateCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetResponseListModel]:
    # Set created_at and updated_at to UTC+8 timezone
    now_utc8 = datetime.now(UTC_PLUS_8)
    
    new_cabinet = Cabinet(
        household_id=request_model.household_id,
        room_id=request_model.room_id,
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
        cabinet_name_new=cast(str, new_cabinet.name),
        db=db
    )
    
    return await read_cabinet(
        ReadCabinetRequestModel(household_id=request_model.household_id),
        db
    )

# ==================== Read ====================
async def read_cabinet(
    request_model: ReadCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetResponseListModel]:
    query = select(Cabinet).where(Cabinet.household_id == request_model.household_id)
    
    if request_model.room_id is not None:
        query = query.where(Cabinet.room_id == request_model.room_id)
    
    if request_model.cabinet_ids is not None and len(request_model.cabinet_ids) > 0:
        query = query.where(Cabinet.id.in_(request_model.cabinet_ids))
    
    result = await db.execute(query)
    cabinets = result.scalars().all()

    if not cabinets:
        return []
    
    cabinets_by_room = await _group_cabinets_by_room(cabinets, db)
    
    response_models = []
    for room_id, cabinet_list in cabinets_by_room.items():
        room_id_str = "" if room_id is None else str(room_id)
        response_models.append(
            CabinetResponseListModel(
                room_id=room_id_str,
                cabinet=cabinet_list
            )
        )
    
    return response_models

# ==================== Update ====================
async def update_cabinet(
    request_model: UpdateCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetResponseListModel]:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == request_model.cabinet_id)
    )
    cabinet = result.scalar_one_or_none()
    
    if not cabinet:
        raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_41)
    
    old_cabinet_name = cast(str, cabinet.name)
    old_room_id = cast(Optional[UUID], cabinet.room_id)
    isRoomChanged = False
    isCabinetNameChanged = False
    
    if request_model.room_id is not None and old_room_id != request_model.room_id:
        cabinet.room_id = request_model.room_id
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
    
    return await read_cabinet(
        ReadCabinetRequestModel(household_id=cast(UUID, cabinet.household_id)),
        db
    )


# ==================== Delete ====================
async def delete_cabinet(
    request_model: DeleteCabinetRequestModel,
    db: AsyncSession
) -> None:
    result = await db.execute(
        select(Cabinet).where(Cabinet.id == request_model.id)
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
    cabinet_name_new: Optional[str] = None,
    room_name_new: Optional[str] = None,
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=household_id,
            user_name=user_name,
            operate_type=operate_type,
            entity_type=EntityType.CABINET.value,
            record_type=RecordType.NORMAL.value,
            cabinet_name_old=cabinet_name_old,
            cabinet_name_new=cabinet_name_new,
            room_name_new=room_name_new,
        ),
        db
    )

async def _group_cabinets_by_room(
    cabinets: List[Cabinet],
    db: AsyncSession
) -> Dict[Optional[UUID], List[CabinetResponseModel]]:
    cabinets_by_room: Dict[Optional[UUID], List[CabinetResponseModel]] = {}
    
    for cabinet in cabinets:
        item_count_result = await db.execute(
            select(func.count(Item.id)).where(Item.cabinet_id == cabinet.id)
        )
        item_count = item_count_result.scalar() or 0
        
        cabinet_model = CabinetResponseModel(
            cabinet_id=cast(UUID, cabinet.id),
            name=cast(str, cabinet.name),
            item_count=item_count
        )
        
        room_id = cast(Optional[UUID], cabinet.room_id)
        if room_id not in cabinets_by_room:
            cabinets_by_room[room_id] = []
        cabinets_by_room[room_id].append(cabinet_model)
    
    return cabinets_by_room