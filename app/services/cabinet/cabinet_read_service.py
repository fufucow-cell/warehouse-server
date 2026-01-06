from typing import Optional, List, Dict, cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from app.schemas.category_request import ReadCategoryRequestModel
from app.schemas.item_response import ItemInCabinetInfo, ItemCategoryResponseModel
from app.services.category.category_read_service import read_category, gen_single_category_tree
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, or_
from app.table.cabinet import Cabinet
from app.table.item import Item
from app.table.item_cabinet_quantity import ItemCabinetQuantity
from app.table.category import Category
from app.schemas.cabinet_request import ReadCabinetRequestModel
from app.schemas.cabinet_response import CabinetResponseModel, CabinetInRoomResponseModel, RoomsResponseModel
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
    request_model: ReadCabinetRequestModel,
    db: AsyncSession,
    include_items: bool = True
) -> List[RoomsResponseModel]:
    # 取出 cabinets
    household_id_str = uuid_to_str(request_model.household_id)
    cabinets_query = select(Cabinet).where(Cabinet.household_id == household_id_str)
    room_ids: List[UUID] = []

    if request_model.room_id is not None:
        cabinets_query = cabinets_query.where(Cabinet.room_id == uuid_to_str(request_model.room_id))
        room_ids.append(request_model.room_id)
    
    result = await db.execute(cabinets_query)
    all_cabinets = list(result.scalars().all())

    if not all_cabinets:
        return []
    
    # 取出 quantity（無論是否包含 items，都需要計算 cabinet 的 quantity）
    all_cabinet_ids = [cabinet.id for cabinet in all_cabinets]
    # 包含所有 cabinets 的 quantities 和所有 cabinet_id 為 NULL 的 quantities
    from sqlalchemy import or_
    quantities_query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.household_id == household_id_str
    ).where(
        or_(
            ItemCabinetQuantity.cabinet_id.in_(all_cabinet_ids),
            ItemCabinetQuantity.cabinet_id.is_(None)
        )
    )

    quantities_result = await db.execute(quantities_query)
    all_quantities = list(quantities_result.scalars().all())
    
    result_rooms = _group_cabinets_by_room(all_cabinets, all_quantities)
    
    # 如果需要包含 items，才執行 items 相關的查詢
    if include_items:
        all_item_ids = list(set([qty.item_id for qty in all_quantities]))

        # 取出 items
        items_query = select(Item).where(Item.household_id == household_id_str).where(Item.id.in_(all_item_ids))
        all_items_result = await db.execute(items_query)
        all_items = list(all_items_result.scalars().all())

        # 取得所有分類
        categories_query = select(Category).where(Category.household_id == household_id_str)
        all_category_result = await db.execute(categories_query)
        all_category = list(all_category_result.scalars().all())
        _group_items_by_cabinet(result_rooms, all_items, all_category, all_quantities, db)
    
    return result_rooms

# 兼容舊的 API，用於 item_service.py
async def read_cabinet(
    request_model: ReadCabinetRequestModel,
    db: AsyncSession
) -> List[CabinetInRoomResponseModel]:
    rooms_result = await read_cabinet_by_room(
        ReadCabinetRequestModel(
            household_id=request_model.household_id,
            room_id=request_model.room_id  # 使用传入的 room_id
        ),
        db,
        include_items=False  # 不需要 items，只返回 cabinet 信息
    )
    # 扁平化 RoomsResponseModel 列表为 CabinetInRoomResponseModel 列表
    result: List[CabinetInRoomResponseModel] = []
    for room in rooms_result:
        for cabinet in room.cabinets:
            # 如果指定了 cabinet_id，进行过滤
            if request_model.cabinet_id is not None:
                if cabinet.id is not None and cabinet.id == request_model.cabinet_id:
                    result.append(cabinet)
            else:
                result.append(cabinet)
    return result

# ==================== Private Method ====================

def _group_cabinets_by_room(
    cabinets: List[Cabinet],
    quantities: List[ItemCabinetQuantity],
) -> List[RoomsResponseModel]:
    # 構建 cabinet_id 到總 quantity 的映射
    cabinet_quantities_dict: Dict[str, int] = {}
    for qty in quantities:
        # 如果 cabinet_id 為 None，轉換成 "empty"
        cabinet_id = qty.cabinet_id if qty.cabinet_id is not None else "empty"
        if cabinet_id not in cabinet_quantities_dict:
            cabinet_quantities_dict[cabinet_id] = 0
        cabinet_quantities_dict[cabinet_id] += qty.quantity
    
    # 按照 room_id 分組
    result_dict: Dict[str, List[CabinetInRoomResponseModel]] = {}
    
    for cabinet in cabinets:
        # 確定 room_id（None 時使用 "empty"）
        if cabinet.room_id is None:
            room_id = "empty"
        else:
            room_id = cast(str, cabinet.room_id)
        
        # 初始化 room 的列表（如果不存在）
        if room_id not in result_dict:
            result_dict[room_id] = []
        
        # 從 quantity table 中獲取該 cabinet 的總 quantity
        cabinet_id_str = uuid_to_str(cabinet.id)
        cabinet_total_quantity = cabinet_quantities_dict.get(cabinet_id_str, 0)
        
        # 創建 CabinetInRoomResponseModel
        cabinet_model = CabinetInRoomResponseModel(
            id=cast(UUID, cabinet.id),
            name=cast(str, cabinet.name),
            quantity=cabinet_total_quantity,  # 從 quantity table 加總
            items=[]  # 初始值，後續會更新
        )
        
        result_dict[room_id].append(cabinet_model)
    
    # 轉換為 RoomsResponseModel 列表
    result: List[RoomsResponseModel] = []
    for room_id_str, cabinet_list in result_dict.items():
        # 計算該 room 的總 quantity
        total_quantity = sum(cab.quantity for cab in cabinet_list)
        
        # room_id 為 "empty" 時轉換為 None，否則保持原值
        room_id_final = None if room_id_str == "empty" else room_id_str
        
        result.append(
            RoomsResponseModel(
                room_id=room_id_final,
                quantity=total_quantity,
                cabinets=cabinet_list
            )
        )
    
    return result

def _group_items_by_cabinet(
    rooms: List[RoomsResponseModel],
    items: List[Item],
    categories: List[Category],
    quantities: List[ItemCabinetQuantity],
    db: AsyncSession,
) -> None:
    # 構建 item id 到 Item 的映射
    items_dict: Dict[str, Item] = {str(item.id): item for item in items}
    
    # 構建 cabinet_id 到 quantities 的映射：{cabinet_id: {item id: quantity}}
    quantities_by_cabinet: Dict[str, Dict[str, int]] = {}
    for qty in quantities:
        # 如果 cabinet_id 為 None，轉換成 "empty"
        cabinet_id = qty.cabinet_id if qty.cabinet_id is not None else "empty"
        
        if cabinet_id not in quantities_by_cabinet:
            quantities_by_cabinet[cabinet_id] = {}
        quantities_by_cabinet[cabinet_id][qty.item_id] = qty.quantity
    
    # 遍歷每個 room，然後遍歷每個 room 下的 cabinet，組裝 items
    for room in rooms:
        room_total_quantity = 0
        
        for cabinet in room.cabinets:
            # 檢查是否為虛擬櫥櫃（id 為 None）
            if cabinet.id is None:
                cabinet_id = "empty"
            else:
                cabinet_id = str(cabinet.id)
            
            # 獲取該 cabinet 的 quantities
            cabinet_quantities = quantities_by_cabinet.get(cabinet_id, {})
            
            # 組裝該 cabinet 的 items
            cabinet_items: List[ItemInCabinetInfo] = []
            total_quantity = 0
            
            for item_id, quantity in cabinet_quantities.items():
                if quantity > 0 and item_id in items_dict:
                    item = items_dict[item_id]
                    # 生成 category tree
                    category_model = gen_single_category_tree(
                        categories, 
                        cast(UUID, item.category_id) if item.category_id else None
                    )
                    # 將 CategoryResponseModel（children 是 List）轉換為 ItemCategoryResponseModel（child 是單個對象）
                    from app.services.item.item_read_service import _convert_category_to_item_category
                    item_category_model = _convert_category_to_item_category(category_model) if category_model else None
                    # 創建新的 ItemInCabinetInfo 並設置 quantity
                    cabinet_item = ItemInCabinetInfo(
                        id=cast(UUID, item.id),
                        name=cast(str, item.name),
                        description=cast(Optional[str], item.description),
                        quantity=quantity,  # 使用該 cabinet 中的 quantity
                        min_stock_alert=cast(int, item.min_stock_alert),
                        photo=cast(Optional[str], item.photo),
                        category=item_category_model
                    )
                    cabinet_items.append(cabinet_item)
                    total_quantity += quantity
            
            # 更新 cabinet 的 items 和 quantity
            cabinet.items = cabinet_items
            cabinet.quantity = total_quantity
            room_total_quantity += total_quantity
        
        # 更新 room 的總 quantity
        room.quantity = room_total_quantity
    
    # 處理未綁定櫥櫃（cabinet_id 為 NULL 的 items）
    unbound_items_quantities = quantities_by_cabinet.get("empty", {})
    if unbound_items_quantities:
        # 查找是否已經存在 room（room_id 為 None 或 "empty"）
        unbound_room = None
        for room in rooms:
            if room.room_id is None or room.room_id == "empty":
                unbound_room = room
                break
        
        if unbound_room is None:
            # 創建新的 room（用於存放未綁定櫥櫃的物品）
            unbound_cabinet = CabinetInRoomResponseModel(
                id=None,  # 虛擬櫥櫃 ID 為 None
                name=None,  # 虛擬櫥櫃名稱
                quantity=0,
                items=[]
            )
            unbound_room = RoomsResponseModel(
                room_id=None,
                quantity=0,
                cabinets=[unbound_cabinet]
            )
            rooms.append(unbound_room)
        
        # 查找未綁定櫥櫃的 cabinet（id 為 None）
        unbound_cabinet = None
        for cabinet in unbound_room.cabinets:
            if cabinet.id is None:
                unbound_cabinet = cabinet
                break
        
        if unbound_cabinet is None:
            # 創建新的 cabinet（這是一個虛擬的 cabinet，用於存放 cabinet_id 為 NULL 的物品）
            unbound_cabinet = CabinetInRoomResponseModel(
                id=None,  # 虛擬櫥櫃 ID 為 None
                name=None,  # 虛擬櫥櫃名稱
                quantity=0,
                items=[]
            )
            unbound_room.cabinets.append(unbound_cabinet)
        
        # 組裝 cabinet_id 為 NULL 的 items
        unbound_items: List[ItemInCabinetInfo] = []
        unbound_total_quantity = 0
        
        for item_id, quantity in unbound_items_quantities.items():
            if quantity > 0 and item_id in items_dict:
                item = items_dict[item_id]
                # 生成 category tree
                category_model = gen_single_category_tree(
                    categories, 
                    cast(UUID, item.category_id) if item.category_id else None
                )
                # 將 CategoryResponseModel（children 是 List）轉換為 ItemCategoryResponseModel（child 是單個對象）
                from app.services.item.item_read_service import _convert_category_to_item_category
                item_category_model = _convert_category_to_item_category(category_model) if category_model else None
                unbound_item = ItemInCabinetInfo(
                    id=cast(UUID, item.id),
                    name=cast(str, item.name),
                    description=cast(Optional[str], item.description),
                    quantity=quantity,
                    min_stock_alert=cast(int, item.min_stock_alert),
                    photo=cast(Optional[str], item.photo),
                    category=item_category_model
                )
                unbound_items.append(unbound_item)
                unbound_total_quantity += quantity
        
        # 更新 cabinet_id 為 NULL 的 items 和 quantity
        unbound_cabinet.items = unbound_items
        unbound_cabinet.quantity = unbound_total_quantity
        
        # 更新未綁定 room 的總 quantity
        unbound_room.quantity = sum(cab.quantity for cab in unbound_room.cabinets)