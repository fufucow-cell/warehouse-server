from typing import Optional, List, Dict, Set, cast, Any
from uuid import UUID
from app.schemas.cabinet_response import CabinetInRoomResponseModel, CabinetResponseModel, RoomsResponseModel
from app.schemas.item_response import ItemInCabinetInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.table import Item, ItemCabinetQuantity, Cabinet, Category
from app.schemas.item_request import ReadItemRequestModel
from app.schemas.item_response import ItemResponseModel
from app.schemas.category_response import CategoryResponseModel
from app.schemas.item_response import ItemCategoryResponseModel
from app.schemas.cabinet_request import ReadCabinetRequestModel
from app.schemas.category_request import ReadCategoryRequestModel
from app.services.cabinet.cabinet_read_service import read_cabinet
from app.services.category.category_read_service import read_category, gen_single_category_tree
from app.utils.util_uuid import uuid_to_str

# ==================== Read ====================
async def read_item(
    request_model: ReadItemRequestModel,
    db: AsyncSession
) -> List[RoomsResponseModel]:
    household_id_str = uuid_to_str(request_model.household_id)
    items_query = select(Item).where(Item.household_id == household_id_str)
    items_result = await db.execute(items_query)
    all_items = list(items_result.scalars().all())
    
    if not all_items:
        return []
    
    all_item_ids = {item.id for item in all_items}
    category_query = select(Category).where(Category.household_id == household_id_str)
    category_result = await db.execute(category_query)
    all_categories = list(category_result.scalars().all())
    quantities_query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.item_id.in_(all_item_ids),
        ItemCabinetQuantity.household_id == household_id_str
    )
    quantities_result = await db.execute(quantities_query)
    all_quantities = list(quantities_result.scalars().all())
    cabinet_ids_set: Set[Optional[str]] = set()
    
    for qty in all_quantities:
        if qty.cabinet_id is not None:
            cabinet_ids_set.add(qty.cabinet_id)
    
    all_cabinets: List[Cabinet] = []

    if cabinet_ids_set:
        valid_cabinet_ids = {cid for cid in cabinet_ids_set if cid is not None}

        if valid_cabinet_ids:
            cabinets_query = select(Cabinet).where(
                Cabinet.household_id == household_id_str,
                Cabinet.id.in_(valid_cabinet_ids)
            )
            cabinets_result = await db.execute(cabinets_query)
            all_cabinets = list(cabinets_result.scalars().all())
    
    result_rooms = _group_cabinets_by_room_for_items(all_cabinets)
    result_items = _gen_item_with_category_tree(all_items, all_categories, db)
    _group_items_by_cabinet_for_items(result_rooms, result_items, all_quantities)
    return result_rooms


# ==================== Public Helper Methods ====================

async def build_item_response(
    item: Item,
    household_id: UUID,
    db: AsyncSession,
    cabinet_id: Optional[UUID] = None
) -> ItemResponseModel:
    cabinet_name = None
    cabinet_room_id = None
    category = None
    
    # 從 item_cabinet_quantity 表獲取 cabinet_id（使用指定的 cabinet_id 或第一個找到的）
    cabinet_id_for_lookup = cabinet_id
    if cabinet_id_for_lookup is None:
        # 如果沒有指定，獲取第一個找到的 cabinet_id
        cabinet_qty_query = select(ItemCabinetQuantity).where(
            ItemCabinetQuantity.item_id == item.id
        ).limit(1)
        cabinet_qty_result = await db.execute(cabinet_qty_query)
        cabinet_qty = cabinet_qty_result.scalar_one_or_none()
        if cabinet_qty:
            cabinet_id_for_lookup = cast(UUID, cabinet_qty.cabinet_id)
    
    if cabinet_id_for_lookup is not None:
        cabinets_result = await read_cabinet(
            ReadCabinetRequestModel(
                household_id=household_id,
                cabinet_id=cabinet_id_for_lookup
            ),
            db
        )
        # cabinets_result is List[CabinetInRoomResponseModel]
        if cabinets_result:
            for cabinet_model in cabinets_result:
                # CabinetInRoomResponseModel has id, name, quantity, items
                if cabinet_model.id == cabinet_id_for_lookup:
                    cabinet_name = cabinet_model.name
                    # Note: CabinetInRoomResponseModel doesn't have room_id, 
                    # we need to get it from the original query or leave it None
                    cabinet_room_id = None
                    break
    
    if item.category_id is not None:
        categories_result = await read_category(
            ReadCategoryRequestModel(
                household_id=household_id,
                category_id=cast(UUID, item.category_id)
            ),
            db
        )
        if categories_result:
            category = categories_result[0]
    
    # 從 item_cabinet_quantity 表獲取 quantity
    quantity = 0
    if item.id:
        quantities_dict = await _get_item_quantities_dict({item.id}, cabinet_id_for_lookup, db)
        quantity = quantities_dict.get(item.id, 0)
    
    return ItemResponseModel(
        id=cast(UUID, item.id),
        cabinet_id=cabinet_id_for_lookup,
        cabinet_name=cabinet_name,
        cabinet_room_id=cabinet_room_id,
        category=category,
        name=cast(str, item.name),
        description=cast(Optional[str], item.description),
        quantity=quantity,
        min_stock_alert=cast(int, item.min_stock_alert),
        photo=cast(Optional[str], item.photo)
    )


async def get_cabinet_info(
    cabinet_id: Optional[UUID],
    household_id: UUID,
    db: AsyncSession
) -> Dict[str, Any]:
    """獲取 cabinet 資訊，被 update 服務使用"""
    if cabinet_id is None:
        return {
            "cabinet_id": None,
            "cabinet_name": None,
            "room_id": None
        }
    
    cabinets_result = await read_cabinet(
        ReadCabinetRequestModel(
            household_id=household_id,
            cabinet_id=cabinet_id
        ),
        db
    )
    
    cabinet_name = None
    room_id = None
    
    if cabinets_result:
        cabinet_id_uuid = UUID(str(cabinet_id))
        for cabinet_model in cabinets_result:
            if cabinet_model.id == cabinet_id_uuid:
                cabinet_name = cabinet_model.name
                # CabinetInRoomResponseModel doesn't have room_id, need to query from database
                cabinet_query = select(Cabinet).where(Cabinet.id == uuid_to_str(cabinet_id))
                cabinet_result = await db.execute(cabinet_query)
                cabinet = cabinet_result.scalar_one_or_none()
                if cabinet and cabinet.room_id:
                    try:
                        room_id = UUID(cabinet.room_id)
                    except (ValueError, AttributeError):
                        room_id = None
                break
    
    return {
        "cabinet_id": cabinet_id,
        "cabinet_name": cabinet_name,
        "room_id": room_id
    }


async def get_category_info(
    category_id: Optional[UUID],
    household_id: UUID,
    db: AsyncSession
) -> Dict[str, Any]:
    if category_id is None:
        return {
            "category_id": None,
            "level_name": None
        }
    
    from app.services.category.category_read_service import get_level_names
    
    level_names = await get_level_names(
        category_id=category_id,
        db=db
    )
    level_name = " > ".join(level_names) if level_names else None
    return {
        "category_id": category_id,
        "level_name": level_name
    }


# ==================== Private Methods ====================

async def _get_cabinets_dict(
    household_id: UUID,
    cabinet_ids: Set[UUID],
    db: AsyncSession
) -> Dict[UUID, Dict[str, Any]]:
    cabinets_dict = {}
    if cabinet_ids:
        # 直接查询 Cabinet 表以提高效率
        household_id_str = uuid_to_str(household_id)
        cabinet_ids_str = [uuid_to_str(cid) for cid in cabinet_ids]
        cabinet_query = select(Cabinet).where(
            Cabinet.household_id == household_id_str,
            Cabinet.id.in_(cabinet_ids_str)
        )
        cabinet_result = await db.execute(cabinet_query)
        cabinets = list(cabinet_result.scalars().all())
        
        for cabinet in cabinets:
            cabinet_id_uuid = cast(UUID, cabinet.id)
            room_id = None
            if cabinet.room_id:
                try:
                    room_id = UUID(cabinet.room_id)
                except (ValueError, AttributeError):
                    room_id = None
            cabinets_dict[cabinet_id_uuid] = {
                "cabinet_id": cabinet_id_uuid,
                "cabinet_name": cast(str, cabinet.name),
                "room_id": room_id
            }
    return cabinets_dict


async def _get_categories_dict(
    household_id: UUID,
    category_ids: Set[UUID],
    db: AsyncSession
) -> Dict[UUID, CategoryResponseModel]:
    categories_dict = {}
    
    if category_ids:
        for category_id in category_ids:
            categories_result = await read_category(
                ReadCategoryRequestModel(
                    household_id=household_id,
                    category_id=category_id
                ),
                db
            )
            if categories_result:
                categories_dict[category_id] = categories_result[0]
    return categories_dict


async def _get_item_quantities_dict(
    item_ids: Set[str],
    cabinet_id: Optional[UUID],
    db: AsyncSession
) -> Dict[str, int]:
    quantities_dict: Dict[str, int] = {}
    
    if not item_ids:
        return quantities_dict
    
    query = select(ItemCabinetQuantity).where(
        ItemCabinetQuantity.item_id.in_(item_ids)
    )
    
    # 如果指定了 cabinet_id，只查詢該 cabinet 的 quantity
    if cabinet_id is not None:
        query = query.where(ItemCabinetQuantity.cabinet_id == uuid_to_str(cabinet_id))
    
    result = await db.execute(query)
    quantities = list(result.scalars().all())
    
    for qty in quantities:
        item_id = qty.item_id
        if item_id in quantities_dict:
            quantities_dict[item_id] += qty.quantity
        else:
            quantities_dict[item_id] = qty.quantity
    
    return quantities_dict


# ==================== Helper Functions for read_item ====================

def _gen_item_with_category_tree(
    items: List[Item],
    categories: List[Category],
    db: AsyncSession
) -> List[ItemInCabinetInfo]:
    result: List[ItemInCabinetInfo] = []

    for item in items:
        category_model = gen_single_category_tree(
            categories, 
            cast(UUID, item.category_id) if item.category_id else None
        )
        # 將 CategoryResponseModel（children 是 List）轉換為 ItemCategoryResponseModel（child 是單個對象）
        item_category_model = _convert_category_to_item_category(category_model) if category_model else None
        
        result.append(
            ItemInCabinetInfo(
                id=cast(UUID, item.id),
                name=cast(str, item.name),
                description=cast(Optional[str], item.description),
                quantity=0,  # 初始值，後續會更新
                min_stock_alert=cast(int, item.min_stock_alert),
                photo=cast(Optional[str], item.photo),
                category=item_category_model
            )
        )

    return result

def _convert_category_to_item_category(
    category: Optional[CategoryResponseModel]
) -> Optional[ItemCategoryResponseModel]:
    """將 CategoryResponseModel（children 是 List）轉換為 ItemCategoryResponseModel（child 是單個對象）"""
    if category is None:
        return None
    
    # 如果有 children 列表，只取第一個作為 child
    child = None
    if category.children and len(category.children) > 0:
        child = _convert_category_to_item_category(category.children[0])
    
    return ItemCategoryResponseModel(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        child=child
    )

def _group_cabinets_by_room_for_items(
    cabinets: List[Cabinet],
) -> List[RoomsResponseModel]:
    """按 room 分組 cabinets，包含 room_id 為空值的 cabinets"""
    result_dict: Dict[str, List[CabinetResponseModel]] = {}
    
    for cabinet in cabinets:
        cabinet_model = CabinetResponseModel(
            cabinet_id=cast(UUID, cabinet.id),
            room_id=cast(Optional[UUID], cabinet.room_id),
            name=cast(str, cabinet.name),
            quantity=0,  # 初始值，後續會更新
            items=[]  # 初始值，後續會更新
        )

        # room_id 為 None 或空值時，使用 "" 作為 key
        if cabinet.room_id is None or cabinet.room_id == "":
            room_id = ""
        else:
            room_id = str(cabinet.room_id)

        if room_id not in result_dict:
            result_dict[room_id] = []

        result_dict[room_id].append(cabinet_model)
    
    result: List[RoomsResponseModel] = []
    for room_id, cabinet_list in result_dict.items():
        # 將 CabinetResponseModel 轉換為 CabinetInRoomResponseModel
        cabinet_in_room_list: List[CabinetInRoomResponseModel] = []
        for cabinet_model in cabinet_list:
            if cabinet_model.cabinet_id is not None:
                cabinet_in_room_list.append(
                    CabinetInRoomResponseModel(
                        id=cabinet_model.cabinet_id,
                        name=cabinet_model.name,
                        quantity=cabinet_model.quantity or 0,
                        items=cabinet_model.items or []
                    )
                )
        
        # 計算所有 cabinets 的 quantity 總和
        room_quantity = sum(cabinet.quantity for cabinet in cabinet_in_room_list)
        
        result.append(
            RoomsResponseModel(
                room_id=room_id if room_id != "" else None,
                quantity=room_quantity,
                cabinets=cabinet_in_room_list
            )
        )

    return result


def _group_items_by_cabinet_for_items(
    rooms: List[RoomsResponseModel],
    items: List[ItemInCabinetInfo],
    quantities: List[ItemCabinetQuantity],
) -> None:
    # 構建 item id 到 ItemInCabinetInfo 的映射
    items_dict: Dict[str, ItemInCabinetInfo] = {str(item.id): item for item in items}
    
    # 構建 cabinet_id 到 quantities 的映射：{cabinet_id: {item id: quantity}}
    quantities_by_cabinet: Dict[str, Dict[str, int]] = {}
    for qty in quantities:
        # 如果 cabinet_id 為 None，轉換成 "empty"
        cabinet_id = qty.cabinet_id if qty.cabinet_id is not None else "empty"
        
        if cabinet_id not in quantities_by_cabinet:
            quantities_by_cabinet[cabinet_id] = {}
        quantities_by_cabinet[cabinet_id][qty.item_id] = qty.quantity
    
    # 遍歷每個 room 中的 cabinet，組裝 items
    for room in rooms:
        for cabinet in room.cabinets:
            if cabinet.id is None:
                cabinet_id = "empty"
            else:
                # 使用 cabinet.id 來查找對應的 quantities
                cabinet_id = str(cabinet.id)
            
            # 獲取該 cabinet 的 quantities
            cabinet_quantities = quantities_by_cabinet.get(cabinet_id, {})
            
            # 組裝該 cabinet 的 items
            cabinet_items: List[ItemInCabinetInfo] = []
            total_quantity = 0
            
            for item_id, quantity in cabinet_quantities.items():
                if item_id in items_dict:
                    item = items_dict[item_id]
                    # 創建新的 ItemInCabinetInfo 並設置 quantity
                    cabinet_item = ItemInCabinetInfo(
                        id=item.id,
                        name=item.name,
                        description=item.description,
                        quantity=quantity,  # 使用該 cabinet 中的 quantity
                        min_stock_alert=item.min_stock_alert,
                        photo=item.photo,
                        category=item.category
                    )
                    cabinet_items.append(cabinet_item)
                    total_quantity += quantity
            
            # 更新 cabinet 的 items 和 quantity
            cabinet.items = cabinet_items
            cabinet.quantity = total_quantity
            
            # 更新 room 的 quantity（所有 cabinets 的 quantity 總和）
            room.quantity = sum(cab.quantity for cab in room.cabinets)
    
    # 處理 cabinet_id 為 NULL 的 items）
    unbound_items_quantities = quantities_by_cabinet.get("empty", {})
    if unbound_items_quantities:
        # 查找或創建 room_id 為空值（""）的 room
        empty_room = None
        for room in rooms:
            if room.room_id == "" or room.room_id is None:
                empty_room = room
                break
        
        if empty_room is None:
            # 如果不存在 room_id 為空值的 room，創建一個
            empty_room = RoomsResponseModel(room_id=None, quantity=0, cabinets=[])
            rooms.append(empty_room)
        
        # 查找是否已經存在 cabinet（id 為 None 的虛擬櫥櫃）
        unbound_cabinet = None
        for cabinet in empty_room.cabinets:
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
            empty_room.cabinets.append(unbound_cabinet)
        
        # 組裝 cabinet_id 為 NULL 的 items
        unbound_items: List[ItemInCabinetInfo] = []
        unbound_total_quantity = 0
        
        for item_id, quantity in unbound_items_quantities.items():
            if item_id in items_dict:
                item = items_dict[item_id]
                unbound_item = ItemInCabinetInfo(
                    id=item.id,
                    name=item.name,
                    description=item.description,
                    quantity=quantity,
                    min_stock_alert=item.min_stock_alert,
                    photo=item.photo,
                    category=item.category
                )
                unbound_items.append(unbound_item)
                unbound_total_quantity += quantity
        
        # 更新 cabinet_id 為 NULL 的 items 和 quantity
        unbound_cabinet.items = unbound_items
        unbound_cabinet.quantity = unbound_total_quantity
        
        # 更新 room 的 quantity（所有 cabinets 的 quantity 總和）
        empty_room.quantity = sum(cab.quantity for cab in empty_room.cabinets)

