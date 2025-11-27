from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.core_database import Base


class Cabinet(Base):
    """Cabinet 模型 - 橱柜表"""
    __tablename__ = "cabinet"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    room_id = Column(Integer, nullable=True, index=True, comment="房间 ID（关联到 household_server.room.id，可选）")
    home_id = Column(Integer, nullable=False, index=True, comment="家庭 ID（关联到 household_server.home.id）")
    name = Column(String(255), nullable=False, comment="橱柜名称")
    description = Column(String(500), nullable=True, comment="橱柜描述")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    items = relationship("Item", back_populates="cabinet", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Cabinet(id={self.id}, name='{self.name}', room_id={self.room_id})>"

