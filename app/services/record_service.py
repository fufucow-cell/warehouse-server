from typing import List, TypeVar
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.sql import Select, Delete
from app.table.record import Record
from app.schemas.record_request import CreateRecordRequestModel, ReadRecordRequestModel
from app.schemas.record_response import RecordResponseModel
from app.utils.util_uuid import uuid_to_str
import logging

logger = logging.getLogger(__name__)

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

QueryType = TypeVar('QueryType', Select, Delete)

# ==================== Create ====================

async def create_record(
    request_model: CreateRecordRequestModel,
    db: AsyncSession,
) -> None:
    # Set created_at to UTC+8 timezone
    created_at_utc8 = datetime.now(UTC_PLUS_8)
    
    new_record = Record(
        household_id=request_model.household_id,
        item_id=uuid_to_str(request_model.item_id) if request_model.item_id is not None else None,
        user_name=request_model.user_name,
        operate_type=request_model.operate_type,
        entity_type=request_model.entity_type,
        item_name_old=request_model.item_name_old,
        item_name_new=request_model.item_name_new,
        item_description_old=request_model.item_description_old,
        item_description_new=request_model.item_description_new,
        item_photo_old=request_model.item_photo_old,
        item_photo_new=request_model.item_photo_new,
        category_name_old=request_model.category_name_old,
        category_name_new=request_model.category_name_new,
        room_name_old=request_model.room_name_old,
        room_name_new=request_model.room_name_new,
        cabinet_name_old=request_model.cabinet_name_old,
        cabinet_name_new=request_model.cabinet_name_new,
        quantity_count_old=request_model.quantity_count_old,
        quantity_count_new=request_model.quantity_count_new,
        min_stock_count_old=request_model.min_stock_count_old,
        min_stock_count_new=request_model.min_stock_count_new,
        description=request_model.description,
        created_at=created_at_utc8,
    )
    db.add(new_record)
    await db.flush()

# ==================== Read ====================

async def read_record(
    request_model: ReadRecordRequestModel,
    db: AsyncSession,
) -> List[RecordResponseModel]:
    query = select(Record).where(Record.household_id == request_model.household_id)
    query = _apply_record_filters(query, request_model)
    query = query.order_by(Record.created_at.desc())
    result = await db.execute(query)
    records = list(result.scalars().all())
    
    response_models = []
    for record in records:
        # Convert datetime to epoch milliseconds (assuming stored time is in UTC+8)
        if record.created_at:
            # If the datetime is timezone-aware, convert to UTC+8 if needed
            if record.created_at.tzinfo is None:
                # If naive datetime, assume it's UTC+8
                created_at_utc8 = record.created_at.replace(tzinfo=UTC_PLUS_8)
            else:
                # Convert to UTC+8
                created_at_utc8 = record.created_at.astimezone(UTC_PLUS_8)
            created_at_ms = int(created_at_utc8.timestamp() * 1000)
        else:
            created_at_ms = None
        
        # 辅助函数：如果两个值都为 None，返回 None；否则返回列表（不包含 None 值）
        def make_list(old_val, new_val):
            if old_val is None and new_val is None:
                return None
            result = []
            if old_val is not None:
                result.append(old_val)
            if new_val is not None:
                result.append(new_val)
            return result if result else None
        
        response_model = RecordResponseModel(
            id=UUID(record.id),
            household_id=record.household_id,
            item_id=UUID(record.item_id) if record.item_id else None,
            user_name=record.user_name,
            created_at=created_at_ms,
            operate_type=record.operate_type,
            entity_type=record.entity_type,
            item_name=make_list(record.item_name_old, record.item_name_new),
            item_description=make_list(record.item_description_old, record.item_description_new),
            item_photo=make_list(record.item_photo_old, record.item_photo_new),
            item_min_stock_count=make_list(record.min_stock_count_old, record.min_stock_count_new),
            category_name=make_list(record.category_name_old, record.category_name_new),
            cabinet_name=make_list(record.cabinet_name_old, record.cabinet_name_new),
            cabinet_room_name=make_list(record.room_name_old, record.room_name_new),
            quantity_count=make_list(record.quantity_count_old, record.quantity_count_new)
        )
        response_models.append(response_model)
    
    return response_models

# ==================== Delete ====================

async def delete_record(
    request_model: ReadRecordRequestModel,
    db: AsyncSession,
) -> None:
    query = delete(Record).where(Record.household_id == request_model.household_id)
    query = _apply_record_filters(query, request_model)
    result = await db.execute(query)
    await db.flush()

# ==================== Private Method ====================

def _apply_record_filters(query: QueryType, request_model: ReadRecordRequestModel) -> QueryType:
    if request_model.item_id is not None:
        query = query.where(Record.item_id == uuid_to_str(request_model.item_id))
    if request_model.id is not None:
        query = query.where(Record.id == uuid_to_str(request_model.id))
    if request_model.operate_type is not None:
        query = query.where(Record.operate_type == request_model.operate_type)
    if request_model.entity_type is not None:
        query = query.where(Record.entity_type == request_model.entity_type)
    if request_model.start_date is not None:
        start_datetime_utc8 = datetime.fromtimestamp(request_model.start_date / 1000, tz=UTC_PLUS_8)
        start_datetime_utc = start_datetime_utc8.astimezone(timezone.utc)
        query = query.where(Record.created_at >= start_datetime_utc)
    if request_model.end_date is not None:
        end_datetime_utc8 = datetime.fromtimestamp(request_model.end_date / 1000, tz=UTC_PLUS_8)
        end_datetime_utc = end_datetime_utc8.astimezone(timezone.utc)
        query = query.where(Record.created_at <= end_datetime_utc)
    
    return query