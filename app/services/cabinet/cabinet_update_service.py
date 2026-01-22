from typing import Optional, List, cast, Dict
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table.cabinet import Cabinet
from app.table.record import Record
from app.schemas.cabinet_request import UpdateCabinetRequestModel
from app.schemas.cabinet_response import CabinetInRoomResponseModel, RoomsResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Update ====================
async def update_cabinet(
    request_model: UpdateCabinetRequestModel,
    db: AsyncSession
) -> None:
    # 收集所有需要更新的 cabinet_id
    cabinet_ids = [cabinet_info.cabinet_id for cabinet_info in request_model.cabinets]
    cabinet_ids_str = [uuid_to_str(cid) for cid in cabinet_ids]
    
    # 一次性查询所有需要更新的 cabinets
    cabinets_query = select(Cabinet).where(
        Cabinet.id.in_(cabinet_ids_str),
        Cabinet.household_id == request_model.household_id
    )
    cabinets_result = await db.execute(cabinets_query)
    cabinets_list = list(cabinets_result.scalars().all())
    cabinets_dict: Dict[str, Cabinet] = {cab.id: cab for cab in cabinets_list}
    
    # 检查是否有未找到的 cabinet
    found_cabinet_ids = set(cabinets_dict.keys())
    requested_cabinet_ids = set(cabinet_ids_str)
    missing_cabinet_ids = requested_cabinet_ids - found_cabinet_ids
    if missing_cabinet_ids:
        raise ValidationError(ServerErrorCode.REQUEST_PATH_INVALID_42)
    
    # 生成统一的创建时间
    now_utc8 = datetime.now(UTC_PLUS_8)
    
    # 更新每个 cabinet 并收集需要生成 record 的信息
    records_to_create = []
    for cabinet_info in request_model.cabinets:
        cabinet_id_str = uuid_to_str(cabinet_info.cabinet_id)
        cabinet = cabinets_dict.get(cabinet_id_str)
        
        if not cabinet:
            continue
        
        old_cabinet_name = cast(str, cabinet.name)
        old_room_id_str = cabinet.room_id
        
        is_room_changed = False
        is_cabinet_name_changed = False
        
        # 更新 room_id
        if cabinet_info.new_room_id is not None:
            if old_room_id_str != cabinet_info.new_room_id:
                cabinet.room_id = cabinet_info.new_room_id
                is_room_changed = True
        
        # 更新 cabinet name
        if cabinet_info.new_cabinet_name is not None:
            if not cabinet_info.new_cabinet_name.strip():
                raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
            
            if old_cabinet_name != cabinet_info.new_cabinet_name:
                cabinet.name = cabinet_info.new_cabinet_name
                is_cabinet_name_changed = True
        
        # 如果有变化，更新 updated_at
        if is_cabinet_name_changed or is_room_changed:
            cabinet.updated_at = now_utc8
            
            # 收集需要生成 record 的信息
            records_to_create.append({
                "cabinet_name_old": old_cabinet_name if is_cabinet_name_changed else None,
                "cabinet_name_new": cabinet_info.new_cabinet_name if is_cabinet_name_changed else None,
                "room_name_old": cabinet_info.old_room_name if is_room_changed else None,
                "room_name_new": cabinet_info.new_room_name if is_room_changed else None,
            })
    
    # 提交所有更新
    await db.commit()
    
    # 生成所有 records（使用相同的创建时间）
    if records_to_create:
        await _gen_record(
            household_id_str=request_model.household_id,
            user_name=request_model.user_name,
            records_info=records_to_create,
            created_at=now_utc8,
            db=db
        )


# ==================== Private Method ====================

async def _gen_record(
    household_id_str: str,
    user_name: str,
    records_info: List[Dict[str, Optional[str]]],
    created_at: datetime,
    db: AsyncSession
) -> None:
    for record_info in records_info:
        new_record = Record(
            household_id=household_id_str,
            item_id=None,
            user_name=user_name,
            operate_type=OperateType.UPDATE.value,
            entity_type=EntityType.CABINET.value,
            cabinet_name_old=record_info.get("cabinet_name_old"),
            cabinet_name_new=record_info.get("cabinet_name_new"),
            room_name_old=record_info.get("room_name_old"),
            room_name_new=record_info.get("room_name_new"),
            created_at=created_at,
        )
        db.add(new_record)
    
    # 统一 flush 所有记录
    await db.flush()

