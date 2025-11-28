"""
日志工具函数
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.log_model import Log, StateType, ItemType, OperateType, LogType
import logging

logger = logging.getLogger(__name__)


async def create_log(
    db: AsyncSession,
    home_id: int,
    state: StateType,
    item_type: ItemType,
    user_name: str,
    operate_type: Optional[List[OperateType]] = None,
    log_type: LogType = LogType.NORMAL
) -> Optional[Log]:
    """
    创建操作日志
    
    Args:
        db: 数据库会话
        home_id: 家庭 ID
        state: 操作状态（StateType 枚举：0=新增（create），1=更新（modify），2=删除（delete），后续可能扩充）
        item_type: 物品类型（ItemType 枚举：0=cabinet, 1=item）
        user_name: 用户名
        operate_type: 操作类型列表（List[OperateType]：0=name, 1=description, 2=move, 3=quantity, 4=photo），仅在 state=1（modify）时使用，可包含多个操作类型，后续可能扩充
        log_type: 日志类型（LogType 枚举：0=一般（normal），1=警告（warning），后续可能扩充），默认为 LogType.NORMAL
    
    Returns:
        Optional[Log]: 创建的日志对象，失败时返回 None
    """
    try:
        # 将 OperateType 枚举列表转换为 int 列表
        operate_type_list = None
        if operate_type is not None:
            operate_type_list = [op.value for op in operate_type]
        
        # 对于 int enum，需要使用 .value
        new_log = Log(
            home_id=home_id,
            state=state.value,  # StateType is int enum, use .value
            item_type=item_type.value,  # ItemType is int enum, use .value
            operate_type=operate_type_list,
            user_name=user_name,
            type=log_type.value  # LogType is int enum, use .value
        )
        db.add(new_log)
        await db.commit()
        await db.refresh(new_log)
        return new_log
    except Exception as e:
        logger.error(f"Error creating log: {e}", exc_info=True)
        if db.in_transaction():
            await db.rollback()
        return None

