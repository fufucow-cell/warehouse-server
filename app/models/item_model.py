from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, SmallInteger, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.core_database import Base


class Item(Base):
    """Item 模型 - 物品表"""
    __tablename__ = "item"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    cabinet_id = Column(UUID(as_uuid=True), ForeignKey("cabinet.id", ondelete="CASCADE"), nullable=True, index=True, comment="橱柜 ID（可选，物品可能不属于任何橱柜）")
    room_id = Column(Integer, nullable=True, index=True, comment="房间 ID（关联到 household_server.room.id，可选）")
    home_id = Column(Integer, nullable=False, index=True, comment="家庭 ID（关联到 household_server.home.id）")
    name = Column(String(255), nullable=False, comment="物品名称")
    description = Column(Text, nullable=True, comment="物品描述")
    quantity = Column(Integer, nullable=False, default=0, index=True, comment="物品数量")
    min_stock_alert = Column(Integer, nullable=False, default=0, comment="最低库存警报阈值")
    photo = Column(String(500), nullable=True, comment="照片 URL")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    cabinet = relationship("Cabinet", back_populates="items")
    categories = relationship("Category", secondary="item_category", back_populates="items")
    logs = relationship("ItemLog", back_populates="item", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Item(id={self.id}, name='{self.name}', quantity={self.quantity}, cabinet_id={self.cabinet_id})>"


class ItemLog(Base):
    """ItemLog 模型 - 物品异动日志表"""
    __tablename__ = "item_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("item.id", ondelete="CASCADE"), nullable=False, index=True, comment="物品 ID")
    type = Column(
        SmallInteger,
        nullable=False,
        index=True,
        comment="日志类型：1=一般信息异动记录，2=告警类型（数量低于条件）"
    )
    log_message = Column(Text, nullable=False, comment="异动日志内容")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # 关系
    item = relationship("Item", back_populates="logs")
    
    # 添加检查约束
    __table_args__ = (
        CheckConstraint("type IN (1, 2)", name="check_item_log_type"),
    )
    
    def __repr__(self):
        return f"<ItemLog(id={self.id}, item_id={self.item_id}, type={self.type}, created_at={self.created_at})>"


class ItemCategory(Base):
    """ItemCategory 模型 - 物品与分类关联表（多对多关系）"""
    __tablename__ = "item_category"
    
    item_id = Column(UUID(as_uuid=True), ForeignKey("item.id", ondelete="CASCADE"), primary_key=True, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("category.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<ItemCategory(item_id={self.item_id}, category_id={self.category_id})>"

