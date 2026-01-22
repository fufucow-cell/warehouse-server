from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.base import Base
from app.core.core_config import settings


class Cabinet(Base):
    __tablename__ = "cabinet"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    room_id = Column(String(255), nullable=True, index=True)
    household_id = Column(String(255), nullable=False, index=True)
    name = Column(String(settings.TABLE_MAX_LENGTH_NAME), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Item 和 Cabinet 的關係已改為通過 item_cabinet_quantity 表維護多對多關係
    
    def __repr__(self):
        return f"<Cabinet(id={self.id}, name='{self.name}', room_id={self.room_id})>"
