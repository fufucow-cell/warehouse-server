from typing import List, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.sql import Select, Delete
from app.table.record import Record
from app.schemas.record_request import CreateRecordRequestModel, RecordRequestModel
from app.schemas.record_response import RecordResponseModel
import logging

logger = logging.getLogger(__name__)

QueryType = TypeVar('QueryType', Select, Delete)

# ==================== Create ====================

async def create_record(
    request_model: CreateRecordRequestModel,
    db: AsyncSession,
) -> None:
    new_record = Record(
        household_id=request_model.household_id,
        user_name=request_model.user_name,
        operate_type=request_model.operate_type,
        entity_type=request_model.entity_type,
        record_type=request_model.record_type,
        item_name_old=request_model.item_name_old,
        item_name_new=request_model.item_name_new,
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
    )
    db.add(new_record)
    await db.flush()

# ==================== Read ====================

async def read_record(
    request_model: RecordRequestModel,
    db: AsyncSession,
) -> List[RecordResponseModel]:
    query = select(Record).where(Record.household_id == request_model.household_id)
    query = _apply_record_filters(query, request_model)
    query = query.order_by(Record.created_at.desc())
    result = await db.execute(query)
    records = result.scalars().all()
    return [RecordResponseModel.model_validate(record) for record in records]

# ==================== Delete ====================

async def delete_record(
    request_model: RecordRequestModel,
    db: AsyncSession,
) -> None:
    query = delete(Record).where(Record.household_id == request_model.household_id)
    query = _apply_record_filters(query, request_model)
    result = await db.execute(query)
    await db.flush()

# ==================== Private Method ====================

def _apply_record_filters(query: QueryType, request_model: RecordRequestModel) -> QueryType:
    if request_model.operate_type is not None:
        query = query.where(Record.operate_type == request_model.operate_type)
    if request_model.entity_type is not None:
        query = query.where(Record.entity_type == request_model.entity_type)
    if request_model.record_type is not None:
        query = query.where(Record.record_type == request_model.record_type)
    if request_model.start_date is not None:
        query = query.where(Record.created_at >= request_model.start_date)
    if request_model.end_date is not None:
        query = query.where(Record.created_at <= request_model.end_date)
    
    return query