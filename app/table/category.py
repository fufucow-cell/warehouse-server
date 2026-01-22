from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.base import Base
from app.core.core_config import settings


class Category(Base):
    __tablename__ = "category"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    household_id = Column(String(255), nullable=False, index=True)
    name = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=False)
    parent_id = Column(String(36), ForeignKey("category.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    parent = relationship("Category", remote_side=[id], backref="children")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', household_id={self.household_id})>"
