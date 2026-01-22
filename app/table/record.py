from sqlalchemy import Column, Integer, String, DateTime, SmallInteger
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
    ITEM_NORMAL = 1 # 物品資訊
    CATEGORY = 2  # 分类
    ITEM_QUANTITY = 3 # 物品數量
    ITEM_POSITION = 4 # 物品位置


class Record(Base):
    __tablename__ = "record"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    item_id = Column(String(36), nullable=True, index=True)
    household_id = Column(String(255), nullable=False, index=True)
    user_name = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=False)
    operate_type = Column(SmallInteger, nullable=False, index=True)
    entity_type = Column(SmallInteger, nullable=False, index=True)
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
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<Record(id={self.id}, household_id={self.household_id}, user_name='{self.user_name}', operate_type={self.operate_type}, entity_type={self.entity_type}, created_at={self.created_at})>"
