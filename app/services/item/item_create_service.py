from typing import cast, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from openai import OpenAI
from app.table import Item, ItemCabinetQuantity, Category
from app.schemas.item_request import CreateItemRequestModel, CreateItemSmartRequestModel
from app.schemas.item_response import ItemResponseModel, ItemOpenAIRecognitionResult
from app.schemas.record_request import CreateRecordRequestModel
from app.table.record import OperateType, EntityType
from app.services.record_service import create_record
from app.services.category.category_create_service import create_category
from app.schemas.category_request import CreateCategoryRequestModel
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_error_handle import ValidationError
from app.utils.util_file import validate_base64_image, save_base64_image
from app.utils.util_uuid import uuid_to_str
from app.utils.util_log import log_openai_result
from app.core.core_config import settings

# UTC+8 timezone (China Standard Time)
UTC_PLUS_8 = timezone(timedelta(hours=8))

# ==================== Create ====================
async def create_item(
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> ItemResponseModel:
    photo_url = None

    if request_model.photo is not None:
        if not validate_base64_image(request_model.photo):
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)

        photo_url = save_base64_image(request_model.photo)

        if not photo_url:
            raise ValidationError(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # Set created_at and updated_at to UTC+8 timezone
    now_utc8 = datetime.now(UTC_PLUS_8)
    
    # 創建 item（不再包含 cabinet_id，通過 item_cabinet_quantity 表維護）
    new_item = Item(
        household_id=request_model.household_id,
        category_id=uuid_to_str(request_model.category_id) if request_model.category_id is not None else None,
        name=request_model.name,
        description=request_model.description,
        min_stock_alert=request_model.min_stock_alert,
        photo=photo_url,
        created_at=now_utc8,
        updated_at=now_utc8,
    )
    db.add(new_item)
    await db.flush()
    
    # 總是創建 item_cabinet_quantity 記錄，cabinet_id 可以為 null，quantity 沒有值就自動補 0
    quantity = request_model.quantity if request_model.quantity > 0 else 0
    cabinet_id = uuid_to_str(request_model.cabinet_id) if request_model.cabinet_id is not None else None
    item_cabinet_qty = ItemCabinetQuantity(
            household_id=request_model.household_id,
            item_id=new_item.id,
            cabinet_id=cabinet_id,
            quantity=quantity,
            created_at=now_utc8,
            updated_at=now_utc8,
        )
    db.add(item_cabinet_qty)
    await db.flush()
        
    # 創建 record
    new_item_model = _build_item_response(
        item=new_item,
        cabinet_id=request_model.cabinet_id,
        quantity=quantity
    )
    await _gen_record(new_item_model, request_model, db)
    return new_item_model


# ==================== Private Method ====================

async def _gen_record(
    item_model: ItemResponseModel,
    request_model: CreateItemRequestModel,
    db: AsyncSession
) -> None:
    await create_record(
        CreateRecordRequestModel(
            household_id=request_model.household_id,
            item_id=item_model.id,
            user_name=request_model.user_name,
            operate_type=OperateType.CREATE.value,
            entity_type=EntityType.ITEM_NORMAL.value,
            item_name_new=item_model.name,
            item_description_new=item_model.description,
            item_photo_new=item_model.photo,
            cabinet_name_new=item_model.cabinet_name,
            category_name_new=item_model.category.name if item_model.category else None,
            quantity_count_new=item_model.quantity,
            min_stock_count_new=item_model.min_stock_alert,
        ),
        db
    )
    
def _build_item_response(
    item: Item,
    cabinet_id: Optional[UUID] = None,
    quantity: int = 0
) -> ItemResponseModel:
    return ItemResponseModel(
        id=cast(UUID, item.id),
        cabinet_id=cabinet_id,
        cabinet_name=None,
        cabinet_room_id=None,
        category=None,
        name=cast(str, item.name),
        description=cast(Optional[str], item.description),
        quantity=quantity,
        min_stock_alert=cast(int, item.min_stock_alert),
        photo=cast(Optional[str], item.photo)
    )

# ==================== Public Method ====================

async def recognize_item_from_image(
    request_model: CreateItemSmartRequestModel,
    db: AsyncSession,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_name: Optional[str] = None
) -> Optional[ItemOpenAIRecognitionResult]:
    try:
        # 查詢該 household 的所有 category
        categories_query = select(Category).where(Category.household_id == request_model.household_id)
        categories_result = await db.execute(categories_query)
        categories = categories_result.scalars().all()
        
        # 用 Set 收集所有的 category name
        existing_category_names = {category.name for category in categories}
        
        # 處理 base64 字符串：如果包含 data URI 前綴，提取純 base64 部分
        base64_data = request_model.image
        image_mime_type = "image/jpeg"  # 默認使用 jpeg
        
        if base64_data.startswith("data:image/"):
            # 解析 data URI
            header, base64_data = base64_data.split(",", 1)
            # 從 header 中提取 MIME 類型
            if "jpeg" in header.lower() or "jpg" in header.lower():
                image_mime_type = "image/jpeg"
            elif "png" in header.lower():
                image_mime_type = "image/png"
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # 構建提示詞，使用實際的 category names
        category_names_text = ", ".join(sorted(existing_category_names)) if existing_category_names else "Miscellaneous"
        prompt = f"""Analyze the provided image and identify the primary item. 

                    ### Task:
                    1. Identify the item including brand, color, material, and size/model if visible.
                    2. Select the most appropriate category from the available list below. If no existing category accurately represents the item, create a precise new category name.
                    
                    Available categories: {category_names_text}

                    ### Category Selection Rules:
                    - **STRICT MATCHING**: Only use an existing category if it accurately and specifically represents the item. Do NOT force-fit items into inappropriate categories.
                    - **Examples of WRONG categorization**:
                      * Tea cup → "食品" (Food) ❌ Should be "茶具" (Tea Set)
                      * Sports shoes → "新類別" (New Category) ❌ Should be "鞋類" (Footwear)
                    - **When to create a new category**:
                      * If the item belongs to a distinct type that is NOT represented in the available categories
                      * The new category name must be specific, accurate, and in **{request_model.language}** (e.g., "茶具", "鞋類", "電子產品")
                    - **FORBIDDEN**: Never return placeholder terms like "新類別", "新类别", "New Category", or any generic labels. Always return a specific, meaningful category name.

                    ### Output Requirements:
                    - ALL fields must be in **{request_model.language}**.
                    - Strictly follow the JSON schema below.
                    - Do not include any markdown formatting (like ```json) in the raw response, just the JSON object.

                    ### JSON Fields:
                    - "name": A concise but descriptive title (e.g., "Apple iPhone 15 Pro, Natural Titanium").
                    - "description": A detailed paragraph describing distinctive features, condition, and visual details.
                    - "category": Either an exact match from the available categories list, OR a precise new category name (1-3 words) if no existing category fits. MUST be a specific, meaningful category name - NO placeholders allowed.
                    - "confidence": An integer from 0-100 reflecting your certainty.

                    ### Language Restriction:
                    - Language: {request_model.language} (Mandatory for all text fields)
                    
                    ### Critical Rule for Category Field:
                    - Return ONLY the category name, nothing else. Do NOT add prefixes, labels, or explanations.
                    - If creating a new category, ensure it is specific and accurate (e.g., "茶具" for tea cups, "鞋類" for shoes, "運動器材" for sports equipment).
                    - NEVER return generic placeholders like "新類別", "新类别", "新分类", or "New Category"."""

        # 調用 OpenAI Vision API
        response = client.chat.completions.create(
            model=settings.OPENAI_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_mime_type};base64,{base64_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("No response from AI")
        
        # 記錄 OpenAI 響應到日誌
        try:
            # 將 OpenAI 響應轉換為可序列化的格式
            openai_response_data = {
                "content": content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                    "total_tokens": response.usage.total_tokens if response.usage else None
                } if response.usage else None
            }
            log_openai_result(user_id, request_id, openai_response_data)
        except Exception:
            # 如果記錄日誌失敗，不影響主流程
            pass
        
        # 嘗試解析 JSON 響應
        try:
            # 首先嘗試提取 JSON 對象
            json_string = content.strip()
            
            # 查找 JSON 對象
            json_match = re.search(r'\{[\s\S]*\}', json_string)
            if json_match:
                json_string = json_match.group(0)
            
            result = json.loads(json_string)
            
            # 獲取識別出的 category
            recognized_category = result.get("category", "Miscellaneous").strip()
            
            # 檢查識別出的 category 是否在現有分類中
            category_id = None
            isNewCategory = False
            if recognized_category in existing_category_names:
                # 匹配到現有分類，從 categories 列表中查找對應的 category 並獲取 id
                matched_category = next((cat for cat in categories if cat.name == recognized_category), None)
                if matched_category:
                    category_id = UUID(matched_category.id)
                    isNewCategory = False
            else:
                # 識別出的物品不屬於任何現有分類，使用 category_create_service 創建新的 category
                category_response = await create_category(
                    CreateCategoryRequestModel(
                        household_id=request_model.household_id,
                        name=recognized_category,
                        parent_id=None,
                        user_name=user_name or ""
                    ),
                    db
                )
                # 從返回的 response 中獲取新創建的 category id
                # 如果返回的對象有 children，說明返回的是 parent，新創建的 category 在 children 中
                # 否則，返回的就是新創建的 category 本身
                if category_response.children and len(category_response.children) > 0:
                    # 新創建的 category 在 children 的最後一個位置
                    category_id = category_response.children[-1].id
                else:
                    category_id = category_response.id
                isNewCategory = True
            
            return ItemOpenAIRecognitionResult(
                name=result.get("name", "Unknown Item"),
                description=result.get("description", "No description available"),
                category_id=category_id,
                category=recognized_category,
                is_new_category=isNewCategory,
                confidence=result.get("confidence", 50),
            )
        except (json.JSONDecodeError, KeyError) as parse_error:
            # 如果 JSON 解析失敗，直接拋出錯誤
            raise ValueError(f"Failed to parse OpenAI response: {str(parse_error)}") from parse_error
    except Exception as error:
        # 直接拋出錯誤
        raise

async def recognize_item_from_image_test(
    request_model: CreateItemSmartRequestModel,
    db: AsyncSession,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_name: Optional[str] = None
) -> Optional[ItemOpenAIRecognitionResult]:
    try:
        # 查詢該 household 的所有 category
        categories_query = select(Category).where(Category.household_id == request_model.household_id)
        categories_result = await db.execute(categories_query)
        categories = categories_result.scalars().all()
        
        # 用 Set 收集所有的 category name
        existing_category_names = {category.name for category in categories}
        
        # 讀取日誌文件的最後一筆資料
        project_root = Path(__file__).parent.parent.parent.parent
        log_file_path = project_root / "log" / settings.APP_ENV / "open_ai_result" / "log_2026-01-09.txt"
        
        if not log_file_path.exists():
            raise ValueError(f"Log file not found: {log_file_path}")
        
        # 讀取並解析 JSON 文件
        with open(log_file_path, "r", encoding="utf-8") as f:
            log_entry = json.load(f)
        
        # 提取 content 並解析
        content = log_entry.get("data", {}).get("content", "")
        if not content:
            raise ValueError("No content found in log entry")
        
        result = json.loads(content)
        
        # 獲取識別出的 category
        recognized_category = result.get("category", "Miscellaneous").strip()
        
        # 檢查識別出的 category 是否在現有分類中
        category_id = None
        isNewCategory = False
        if recognized_category in existing_category_names:
            # 匹配到現有分類，從 categories 列表中查找對應的 category 並獲取 id
            matched_category = next((cat for cat in categories if cat.name == recognized_category), None)
            if matched_category:
                category_id = UUID(matched_category.id)
                isNewCategory = False
        else:
            # 識別出的物品不屬於任何現有分類，使用 category_create_service 創建新的 category
            category_response = await create_category(
                CreateCategoryRequestModel(
                    household_id=request_model.household_id,
                    name=recognized_category,
                    parent_id=None,
                    user_name=user_name or ""
                ),
                db
            )
            # 從返回的 response 中獲取新創建的 category id
            # 如果返回的對象有 children，說明返回的是 parent，新創建的 category 在 children 中
            # 否則，返回的就是新創建的 category 本身
            if category_response.children and len(category_response.children) > 0:
                # 新創建的 category 在 children 的最後一個位置
                category_id = category_response.children[-1].id
            else:
                category_id = category_response.id
            isNewCategory = True
        
        return ItemOpenAIRecognitionResult(
            name=result.get("name", "Unknown Item"),
            description=result.get("description", "No description available"),
            category_id=category_id,
            category=recognized_category,
            is_new_category=isNewCategory,
            confidence=result.get("confidence", 50),
        )
    except Exception as error:
        # 直接拋出錯誤
        raise