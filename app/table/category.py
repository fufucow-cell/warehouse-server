from sqlalchemy import Column, SmallInteger, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.base import Base
from app.core.core_config import settings


class Category(Base):
    __tablename__ = "category"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    household_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("category.id", ondelete="CASCADE"), nullable=True, index=True)
    level = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    parent = relationship("Category", remote_side=[id], backref="children")
    
    __table_args__ = (
        CheckConstraint("level IN (1, 2, 3)", name="check_category_level"),
        CheckConstraint(
            "(parent_id IS NULL AND level = 1) OR (parent_id IS NOT NULL AND level IN (2, 3))",
            name="chk_category_level_parent"
        ),
    )
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', level={self.level}, household_id={self.household_id})>"
