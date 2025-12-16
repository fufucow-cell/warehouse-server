from sqlalchemy import Column, Integer, String, DateTime, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import enum
import uuid
from app.db.base import Base
from app.core.core_config import settings


class OperateType(int, enum.Enum):
    CREATE = 0  # 新增
    UPDATE = 1  # 更新
    DELETE = 2  # 删除


class EntityType(int, enum.Enum):
    CABINET = 0  # 橱柜
    ITEM = 1     # 物品
    CATEGORY = 2  # 分类


class RecordType(int, enum.Enum):
    NORMAL = 0  # 一般
    WARNING = 1  # 警告


class Record(Base):
    __tablename__ = "record"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    household_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_name = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=False)
    operate_type = Column(SmallInteger, nullable=False, index=True)
    entity_type = Column(SmallInteger, nullable=False, index=True)
    record_type = Column(SmallInteger, nullable=False, default=RecordType.NORMAL.value, index=True)
    item_name_old = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    item_name_new = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    item_description_old = Column(String(settings.TABLE_MAX_LENGTH_DESCRIPTION), nullable=True)
    item_description_new = Column(String(settings.TABLE_MAX_LENGTH_DESCRIPTION), nullable=True)
    item_photo_old = Column(String(settings.TABLE_MAX_LENGTH_LINK), nullable=True)
    item_photo_new = Column(String(settings.TABLE_MAX_LENGTH_LINK), nullable=True)
    category_name_old = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    category_name_new = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    room_name_old = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    room_name_new = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    cabinet_name_old = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    cabinet_name_new = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=True)
    quantity_count_old = Column(Integer, nullable=True)
    quantity_count_new = Column(Integer, nullable=True)
    min_stock_count_old = Column(Integer, nullable=True)
    min_stock_count_new = Column(Integer, nullable=True)
    description = Column(String(settings.TABLE_MAX_LENGTH_DESCRIPTION), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<Record(id={self.id}, household_id={self.household_id}, user_name='{self.user_name}', operate_type={self.operate_type}, entity_type={self.entity_type}, record_type={self.record_type}, created_at={self.created_at})>"
