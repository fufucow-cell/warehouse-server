from sqlalchemy import Column, Integer, SmallInteger, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.base import Base


class Category(Base):
    """Category 模型 - 分类表，支持最多三层分类层级"""
    __tablename__ = "category"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    home_id = Column(Integer, nullable=False, index=True, comment="家庭 ID（关联到 household_server.home.id）")
    name = Column(String(255), nullable=False, comment="分类名称")
    parent_id = Column(UUID(as_uuid=True), ForeignKey("category.id", ondelete="CASCADE"), nullable=True, index=True, comment="父分类 ID（用于层级关系）")
    level = Column(
        SmallInteger,
        nullable=False,
        comment="分类层级：1=第一层，2=第二层，3=第三层"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    parent = relationship("Category", remote_side=[id], backref="children")
    items = relationship("Item", secondary="item_category", back_populates="categories")
    
    # 添加检查约束
    __table_args__ = (
        CheckConstraint("level IN (1, 2, 3)", name="check_category_level"),
    )
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', level={self.level}, home_id={self.home_id})>"

