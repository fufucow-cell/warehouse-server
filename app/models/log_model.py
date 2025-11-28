from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
import uuid
import enum
from app.core.core_database import Base


class StateType(int, enum.Enum):
    """操作状态枚举"""
    CREATE = 0  # 新增
    MODIFY = 1  # 更新
    DELETE = 2  # 删除


class ItemType(int, enum.Enum):
    """物品类型枚举（区分 item 和 cabinet）"""
    CABINET = 0  # 橱柜
    ITEM = 1     # 物品


class OperateType(int, enum.Enum):
    """操作类型枚举（区分不同的修改操作）"""
    NAME = 0         # 名称修改
    DESCRIPTION = 1  # 描述修改
    MOVE = 2         # 移动（位置变更）
    QUANTITY = 3     # 数量修改
    PHOTO = 4        # 照片修改
    MIN_STOCK_ALERT = 5  # 最低库存警报阈值修改


class LogType(int, enum.Enum):
    """日志类型枚举"""
    NORMAL = 0  # 一般
    WARNING = 1  # 警告


class Log(Base):
    """Log 模型 - 操作日志表，记录用户对 cabinet、item 等的操作"""
    __tablename__ = "log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    home_id = Column(Integer, nullable=False, index=True, comment="家庭 ID（关联到 household_server.home.id）")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True, comment="创建时间")
    state = Column(
        SmallInteger,
        nullable=False,
        comment="操作状态：0=新增（create），1=更新（modify），2=删除（delete），后续可能扩充"
    )
    item_type = Column(
        SmallInteger,
        nullable=False,
        comment="物品类型：0=cabinet（橱柜），1=item（物品），后续可能扩充"
    )
    operate_type = Column(
        ARRAY(SmallInteger),
        nullable=True,
        comment="操作类型数组：0=name（名称），1=description（描述），2=move（移动），3=quantity（数量），4=photo（照片），5=min_stock_alert（最低库存警报阈值）。仅在 state=1（modify）时使用，可包含多个操作类型，后续可能扩充"
    )
    user_name = Column(String(255), nullable=False, comment="用户名")
    type = Column(
        SmallInteger,
        nullable=False,
        default=LogType.NORMAL.value,
        comment="日志类型：0=一般（normal），1=警告（warning），后续可能扩充"
    )
    
    # 添加检查约束
    # 注意：state、item_type、operate_type 和 type 不限制范围，允许后续扩充
    __table_args__ = ()
    
    def __repr__(self):
        return f"<Log(id={self.id}, home_id={self.home_id}, state={self.state}, item_type={self.item_type}, operate_type={self.operate_type}, user_name='{self.user_name}')>"

