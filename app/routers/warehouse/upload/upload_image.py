"""
文件上传路由
处理物品照片上传
"""
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.core_config import settings
from app.utils.util_response import success_response, error_response
from app.utils.util_error_map import ServerErrorCode
from app.utils.util_request import get_request_id, get_user_id_from_header

router = APIRouter()

# 确保上传目录存在（相对于 warehouse_server 根目录）
UPLOAD_BASE_DIR = Path(__file__).parent.parent.parent.parent.parent / settings.UPLOAD_DIR
UPLOAD_BASE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/image", response_class=JSONResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(..., description="图片文件"),
    db: AsyncSession = Depends(get_db)
):
    """
    上传图片文件
    
    支持的文件类型：jpg, jpeg, png, gif, webp
    最大文件大小：10MB
    """
    get_request_id(request)
    
    try:
        # 從 header 獲取 user_id（由 API Gateway 驗證 token 後設置）
        user_id = get_user_id_from_header(request)
        if not user_id:
            return _error_handle(ServerErrorCode.UNAUTHORIZED_42)
        
        # 驗證文件
        validation_error = await _validate_file(file)
        if validation_error:
            return validation_error
        
        # 保存文件
        file_url = await _save_file(file)
        
        # 返回文件 URL
        return success_response(data={"url": file_url})
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error uploading file: {e}", exc_info=True)
        return _error_handle(ServerErrorCode.INTERNAL_SERVER_ERROR_42)


def _error_handle(internal_code: int) -> JSONResponse:
    return error_response(internal_code=internal_code)


async def _validate_file(file: UploadFile) -> Optional[JSONResponse]:
    """
    验证上传的文件
    """
    # 检查文件类型
    file_extension = Path(file.filename).suffix.lower() if file.filename else ""
    if file_extension not in settings.ALLOWED_IMAGE_EXTENSIONS:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 检查文件大小
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    if file_size == 0:
        return _error_handle(ServerErrorCode.REQUEST_PARAMETERS_INVALID_42)
    
    # 重置文件指针，以便后续读取
    await file.seek(0)
    
    return None


async def _save_file(file: UploadFile) -> str:
    """
    保存文件到本地存储，返回文件 URL
    
    Returns:
        str: 文件的 URL 路径（相对于服务器根路径）
    """
    # 生成唯一文件名
    file_extension = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    # 获取环境文件夹（APP_ENV 转大写，如 dev -> DEV）
    env_folder = settings.APP_ENV.upper()
    
    # 创建按环境、日期分组的目录结构（便于管理）
    # uploads/DEV/2025/11/27/uuid.jpg
    from datetime import datetime
    date_dir = datetime.now().strftime("%Y/%m/%d")
    save_dir = UPLOAD_BASE_DIR / env_folder / date_dir
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    file_path = save_dir / unique_filename
    file_content = await file.read()
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # 返回文件 URL（通过 API Gateway 访问）
    # 格式：/uploads/DEV/2025/11/27/uuid.jpg
    file_url = f"/{settings.UPLOAD_DIR}/{env_folder}/{date_dir}/{unique_filename}"
    
    return file_url

