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
    db: AsyncSession,
    include_items: bool = True
) -> List[CabinetInRoomResponseModel]:
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
    
    result_rooms = _group_cabinets_by_room(all_cabinets)
    
    # 如果需要包含 items，才執行 items 相關的查詢
    if include_items:
        all_cabinet_ids = [cabinet.id for cabinet in all_cabinets]
        
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

        quantities_result = await db.execute(quantities_query)
        all_quantities = list(quantities_result.scalars().all())
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
            name=cast(str, cabinet.name)
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
        # 將 CabinetResponseModel 轉換為 CabinetInRoomResponseModel
        for cabinet_model in cabinet_list:
            if cabinet_model.cabinet_id is not None:
                result.append(
                    CabinetInRoomResponseModel(
                        id=cabinet_model.cabinet_id,
                        name=cabinet_model.name,
                        quantity=0,  # 初始值，後續會更新
                        items=[]  # 初始值，後續會更新
                    )
                )

    return result

def _group_items_by_cabinet(
    rooms: List[CabinetInRoomResponseModel],
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
    
    # 遍歷每個 cabinet，組裝 items
    # rooms 是 List[CabinetInRoomResponseModel]，每個元素本身就是一個 cabinet
    for cabinet in rooms:
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
    
    #（cabinet_id 為 NULL 的 items）
    unbound_items_quantities = quantities_by_cabinet.get("empty", {})
    if unbound_items_quantities:
        # 查找是否已經存在 cabinet（id 為 None）
        unbound_cabinet = None
        for cabinet in rooms:
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
            rooms.append(unbound_cabinet)
        
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