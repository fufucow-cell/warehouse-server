from typing import Optional, List, cast, Dict
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table.cabinet import Cabinet
from app.table.record import Record
from app.schemas.cabinet_request import DeleteCabinetRequestModel
from app.table.record import OperateType, EntityType
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Delete ====================
async def delete_cabinet(
    request_model: DeleteCabinetRequestModel,
    db: AsyncSession
) -> None:
    household_id_str = uuid_to_str(request_model.household_id)
    
    # 如果没有提供 cabinets 列表，返回（不执行任何操作）
    if not request_model.cabinets or len(request_model.cabinets) == 0:
        return
    
    # 收集所有需要删除的 cabinet_id
    cabinet_infos = request_model.cabinets
    cabinet_ids = [cabinet_info.cabinet_id for cabinet_info in cabinet_infos]
    cabinet_ids_str = [uuid_to_str(cid) for cid in cabinet_ids]
    
    # 一次性查询所有需要删除的 cabinets
    cabinets_query = select(Cabinet).where(
        Cabinet.id.in_(cabinet_ids_str),
        Cabinet.household_id == household_id_str
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
    
    # 收集需要生成 record 的信息（在删除之前）
    records_to_create = []
    for cabinet_info in cabinet_infos:
        cabinet_id_str = uuid_to_str(cabinet_info.cabinet_id)
        cabinet = cabinets_dict.get(cabinet_id_str)
        if cabinet:
            cabinet_name = cast(str, cabinet.name)
            records_to_create.append({
                "cabinet_name_old": cabinet_name,
                "room_name_old": cabinet_info.old_room_name,
            })
    
    # 删除所有 cabinets
    for cabinet in cabinets_list:
        await db.delete(cabinet)
    
    # 提交所有删除
    await db.commit()
    
    # 生成所有 records（使用相同的创建时间）
    if records_to_create:
        await _gen_record(
            household_id_str=household_id_str,
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
            operate_type=OperateType.DELETE.value,
            entity_type=EntityType.CABINET.value,
            cabinet_name_old=record_info.get("cabinet_name_old"),
            room_name_old=record_info.get("room_name_old"),
            created_at=created_at,
        )
        db.add(new_record)
    
    # 统一 flush 所有记录
    await db.flush()

