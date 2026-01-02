from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.base import Base


class ItemCabinetQuantity(Base):
    __tablename__ = "item_cabinet_quantity"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    household_id = Column(String(36), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("item.id", ondelete="CASCADE"), nullable=False, index=True)
    cabinet_id = Column(String(36), ForeignKey("cabinet.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    item = relationship("Item", foreign_keys=[item_id])
    cabinet = relationship("Cabinet", foreign_keys=[cabinet_id])
    
    # 唯一约束：同一个物品在同一个柜子中只能有一条记录
    __table_args__ = (
        UniqueConstraint('item_id', 'cabinet_id', name='uk_item_cabinet_quantity_item_cabinet'),
    )
    
    def __repr__(self):
        return f"<ItemCabinetQuantity(id={self.id}, item_id={self.item_id}, cabinet_id={self.cabinet_id}, quantity={self.quantity})>"

