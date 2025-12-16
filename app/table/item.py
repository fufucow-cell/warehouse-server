from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.base import Base
from app.core.core_config import settings


class Item(Base):
    __tablename__ = "item"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("category.id", ondelete="SET NULL"), nullable=True, index=True)
    cabinet_id = Column(UUID(as_uuid=True), ForeignKey("cabinet.id", ondelete="SET NULL"), nullable=True, index=True)
    household_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=False)
    description = Column(String(settings.TABLE_MAX_LENGTH_DESCRIPTION), nullable=True)
    quantity = Column(Integer, nullable=False, default=0)
    min_stock_alert = Column(Integer, nullable=False, default=0)
    photo = Column(String(settings.TABLE_MAX_LENGTH_LINK), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    cabinet = relationship("Cabinet", back_populates="items", foreign_keys=[cabinet_id])
    category = relationship("Category", foreign_keys=[category_id])
    
    def __repr__(self):
        return f"<Item(id={self.id}, name='{self.name}', quantity={self.quantity}, cabinet_id={self.cabinet_id})>"
