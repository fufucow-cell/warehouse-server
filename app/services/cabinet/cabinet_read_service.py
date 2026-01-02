from typing import Optional, List, Dict, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from app.schemas.category_request import ReadCategoryRequestModel
from app.schemas.item_response import ItemInCabinetInfo
from app.services.category.category_read_service import read_category, gen_single_category_tree
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, or_
from app.table.cabinet import Cabinet
from app.table.item import Item
from app.table.item_cabinet_quantity import ItemCabinetQuantity
from app.table.category import Category
from app.schemas.cabinet_request import ReadCabinetByRoomRequestModel, ReadCabinetRequestModel
from app.schemas.cabinet_response import CabinetResponseModel, CabinetInRoomResponseModel
from app.schemas.category_response import CategoryResponseModel
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_uuid import uuid_to_str

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Read ====================

async def read_cabinet_by_room(
    request_model: ReadCabinetByRoomRequestModel,
    db: AsyncSession
) -> List[CabinetInRoomResponseModel]:
    # 取出 cabinets
    household_id_str = uuid_to_str(request_model.household_id)
    cabinets_query = select(Cabinet).where(Cabinet.household_id == household_id_str)
    room_ids: List[UUID] = []

    if request_model.room_id is not None:
        cabinets_query = cabinets_query.where(Cabinet.room_id == uuid_to_str(request_model.room_id))
        room_ids.append(request_model.room_id)
    
    all_cabinets = await db.execute(cabinets_query).scalars().all()
    all_cabinet_ids = [cabinet.id for cabinet in all_cabinets]

    if not all_cabinets:
        return []
    
    result_rooms = _group_cabinets_by_room(all_cabinets)
    
    # 取出 quantity
    quantities_query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.household_id == household_id_str)
    
    if request_model.room_id is not None:
        # 包含指定 room 下的 cabinets 的 quantities 和所有 cabinet_id 為 NULL 的 quantities
        from sqlalchemy import or_
        quantities_query = quantities_query.where(
            or_(
                ItemCabinetQuantity.cabinet_id.in_(all_cabinet_ids),
                ItemCabinetQuantity.cabinet_id.is_(None)
            )
        )

    all_quantities = await db.execute(quantities_query).scalars().all()    
    all_item_ids = list(set([qty.item_id for qty in all_quantities]))

    # 取出 items
    items_query = select(Item).where(Item.household_id == household_id_str).where(Item.id.in_(all_item_ids))
    all_items = await db.execute(items_query).scalars().all()

    # 取得所有分類
    categories_query = select(Category).where(Category.household_id == household_id_str)
    all_category = await db.execute(categories_query).scalars().all()

    result_items = await _gen_item_with_category_tree(all_items, all_category, db)
    _group_items_by_cabinet(result_rooms, result_items, all_quantities)
    
    return result_rooms

# 兼容舊的 API，用於 item_service.py
async def read_cabinet(
    request_model: ReadCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetInRoomResponseModel]:
    """
    兼容舊的 read_cabinet API
    使用 ReadCabinetByRoomRequestModel 來實現，忽略 cabinet_ids 參數（因為 read_cabinet_by_room 不支持按 cabinet_ids 過濾）
    """
    return await read_cabinet_by_room(
        ReadCabinetByRoomRequestModel(
            household_id=request_model.household_id,
            room_id=None  # 獲取所有 rooms 的 cabinets
        ),
        db
    )

# ==================== Private Method ====================

def _group_cabinets_by_room(
    cabinets: List[Cabinet],
) -> List[CabinetInRoomResponseModel]:
    result_dict: Dict[str, List[CabinetResponseModel]] = {}
    
    for cabinet in cabinets:
        cabinet_model = CabinetResponseModel(
            cabinet_id=cast(UUID, cabinet.id),
            room_id=cast(Optional[UUID], cabinet.room_id),
            name=cast(str, cabinet.name),
            item_quantity=0,
            items=[]
        )

        if cabinet.room_id is None:
            room_id = "empty"
        else:
            room_id = cast(str, cabinet.room_id)

        if room_id not in result_dict:
            result_dict[room_id] = []

        result_dict[room_id].append(cabinet_model)
    
    result: List[CabinetInRoomResponseModel] = []
    for room_id, cabinet_list in result_dict.items():
        result.append(
            CabinetInRoomResponseModel(
                room_id=room_id if room_id != "empty" else "",
                cabinet=cabinet_list
            )
        )

    return result

def _gen_item_with_category_tree(
    items: List[Item],
    categories: List[Category],
    db: AsyncSession
) -> List[ItemInCabinetInfo]:
    result: List[ItemInCabinetInfo] = []

    for item in items:
        category = gen_single_category_tree(categories, cast(UUID, item.category_id) if item.category_id else None)
        result.append(
            ItemInCabinetInfo(
                item_id=cast(UUID, item.id),
                name=cast(str, item.name),
                description=cast(Optional[str], item.description),
                quantity=0, 
                min_stock_alert=cast(int, item.min_stock_alert),
                photo=cast(Optional[str], item.photo),
                category=category
            )
        )

    return result

def _group_items_by_cabinet(
    rooms: List[CabinetInRoomResponseModel],
    items: List[ItemInCabinetInfo],
    quantities: List[ItemCabinetQuantity],
) -> None:
    # 構建 item_id 到 ItemInCabinetInfo 的映射
    items_dict: Dict[str, ItemInCabinetInfo] = {str(item.item_id): item for item in items}
    
    # 構建 cabinet_id 到 quantities 的映射：{cabinet_id: {item_id: quantity}}
    quantities_by_cabinet: Dict[str, Dict[str, int]] = {}
    for qty in quantities:
        # 如果 cabinet_id 為 None，轉換成 "empty"
        cabinet_id = qty.cabinet_id if qty.cabinet_id is not None else "empty"
        
        if cabinet_id not in quantities_by_cabinet:
            quantities_by_cabinet[cabinet_id] = {}
        quantities_by_cabinet[cabinet_id][qty.item_id] = qty.quantity
    
    # 遍歷每個 room 中的 cabinet，組裝 items
    for room in rooms:
        for cabinet in room.cabinet:
            # 如果 cabinet_id 為 None，轉換成 "empty"
            cabinet_id = str(cabinet.cabinet_id) if cabinet.cabinet_id is not None else "empty"
            
            # 獲取該 cabinet 的 quantities
            cabinet_quantities = quantities_by_cabinet.get(cabinet_id, {})
            
            # 組裝該 cabinet 的 items
            cabinet_items: List[ItemInCabinetInfo] = []
            total_quantity = 0
            
            for item_id, quantity in cabinet_quantities.items():
                if quantity > 0 and item_id in items_dict:
                    item = items_dict[item_id]
                    # 創建新的 ItemInCabinetInfo 並設置 quantity
                    cabinet_item = ItemInCabinetInfo(
                        item_id=item.item_id,
                        name=item.name,
                        description=item.description,
                        quantity=quantity,  # 使用該 cabinet 中的 quantity
                        min_stock_alert=item.min_stock_alert,
                        photo=item.photo,
                        category=item.category
                    )
                    cabinet_items.append(cabinet_item)
                    total_quantity += quantity
            
            # 更新 cabinet 的 items 和 item_quantity
            cabinet.items = cabinet_items
            cabinet.item_quantity = total_quantity
    
    # 處理未綁定櫥櫃的物品（cabinet_id 為 NULL 的 items）
    # 這些物品應該顯示在 room_id 為空值（""）的 room 中，作為一個特殊的 "未綁定櫥櫃" cabinet
    unbound_items_quantities = quantities_by_cabinet.get("empty", {})
    if unbound_items_quantities:
        # 查找或創建 room_id 為空值（""）的 room
        empty_room = None
        for room in rooms:
            if room.room_id == "":
                empty_room = room
                break
        
        if empty_room is None:
            # 如果不存在 room_id 為空值的 room，創建一個
            empty_room = CabinetInRoomResponseModel(room_id="", cabinet=[])
            rooms.append(empty_room)
        
        # 查找是否已經存在 "未綁定櫥櫃" cabinet（cabinet_id 為 None）
        unbound_cabinet = None
        for cabinet in empty_room.cabinet:
            if cabinet.cabinet_id is None:
                unbound_cabinet = cabinet
                break
        
        if unbound_cabinet is None:
            # 創建新的未綁定櫥櫃 cabinet（這是一個虛擬的 cabinet，用於存放未綁定櫥櫃的物品）
            unbound_cabinet = CabinetResponseModel(
                cabinet_id=None,  # 未綁定櫥櫃沒有真實的 cabinet_id
                room_id=None,
                name="未綁定櫥櫃",  # 虛擬櫥櫃名稱
                item_quantity=0,
                items=[]
            )
            empty_room.cabinet.append(unbound_cabinet)
        
        # 組裝未綁定櫥櫃的 items
        unbound_items: List[ItemInCabinetInfo] = []
        unbound_total_quantity = 0
        
        for item_id, quantity in unbound_items_quantities.items():
            if quantity > 0 and item_id in items_dict:
                item = items_dict[item_id]
                unbound_item = ItemInCabinetInfo(
                    item_id=item.item_id,
                    name=item.name,
                    description=item.description,
                    quantity=quantity,
                    min_stock_alert=item.min_stock_alert,
                    photo=item.photo,
                    category=item.category
                )
                unbound_items.append(unbound_item)
                unbound_total_quantity += quantity
        
        # 更新未綁定櫥櫃的 items 和 item_quantity
        unbound_cabinet.items = unbound_items
        unbound_cabinet.item_quantity = unbound_total_quantity