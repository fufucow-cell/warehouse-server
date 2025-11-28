"""
文件工具函数
处理文件删除、路径转换、base64 图片保存等操作
"""
import os
import base64
import uuid
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from app.core.core_config import settings


def delete_uploaded_file(photo_url: Optional[str]) -> bool:
    """
    删除上传的文件
    
    Args:
        photo_url: 照片的 URL 路径（如：/api/v1/warehouse/uploads/2025/11/27/uuid.jpg）
    
    Returns:
        bool: 删除成功返回 True，文件不存在或删除失败返回 False
    """
    if not photo_url:
        return False
    
    try:
        # 将 URL 路径转换为本地文件路径
        # /uploads/DEV/2025/11/27/uuid.jpg -> uploads/DEV/2025/11/27/uuid.jpg
        # 支持完整 URL 或相对路径
        if photo_url.startswith("http://") or photo_url.startswith("https://"):
            # 完整 URL，提取路径部分
            from urllib.parse import urlparse
            parsed = urlparse(photo_url)
            path = parsed.path
        else:
            path = photo_url
        
        # 支持新旧路径格式（兼容性）
        if path.startswith("/api/v1/warehouse/"):
            # 旧格式：/api/v1/warehouse/uploads/DEV/... -> uploads/DEV/...
            relative_path = path.replace("/api/v1/warehouse/", "")
        elif path.startswith(f"/{settings.UPLOAD_DIR}/"):
            # 新格式：/uploads/DEV/... -> uploads/DEV/...
            relative_path = path.replace(f"/{settings.UPLOAD_DIR}/", "")
        elif path.startswith(settings.UPLOAD_DIR):
            relative_path = path
        else:
            # 如果路径格式不正确，尝试直接使用
            relative_path = path.lstrip("/")
        
        # 构建完整文件路径
        # relative_path 格式：uploads/DEV/2025/11/27/uuid.jpg 或 DEV/2025/11/27/uuid.jpg
        upload_base_dir = Path(__file__).parent.parent.parent / settings.UPLOAD_DIR
        if relative_path.startswith(settings.UPLOAD_DIR):
            # 如果包含 uploads 前缀，移除它
            relative_path = relative_path.replace(f"{settings.UPLOAD_DIR}/", "", 1)
        file_path = upload_base_dir / relative_path
        
        # 检查文件是否存在
        if file_path.exists() and file_path.is_file():
            # 删除文件
            file_path.unlink()
            
            # 尝试删除空的父目录（可选，保持目录结构也可以）
            # 这里不删除目录，保持目录结构以便后续使用
            
            return True
        else:
            # 文件不存在，返回 True（认为已经删除）
            return True
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error deleting file {photo_url}: {e}", exc_info=True)
        return False


def get_file_path_from_url(photo_url: Optional[str]) -> Optional[Path]:
    """
    从 URL 获取本地文件路径
    
    Args:
        photo_url: 照片的 URL 路径
    
    Returns:
        Path: 本地文件路径，如果路径无效返回 None
    """
    if not photo_url:
        return None
    
    try:
        # 将 URL 路径转换为本地文件路径
        # 支持完整 URL 或相对路径
        if photo_url.startswith("http://") or photo_url.startswith("https://"):
            # 完整 URL，提取路径部分
            from urllib.parse import urlparse
            parsed = urlparse(photo_url)
            path = parsed.path
        else:
            path = photo_url
        
        # 支持新旧路径格式（兼容性）
        if path.startswith("/api/v1/warehouse/"):
            # 旧格式：/api/v1/warehouse/uploads/DEV/... -> uploads/DEV/...
            relative_path = path.replace("/api/v1/warehouse/", "")
        elif path.startswith(f"/{settings.UPLOAD_DIR}/"):
            # 新格式：/uploads/DEV/... -> uploads/DEV/...
            relative_path = path.replace(f"/{settings.UPLOAD_DIR}/", "")
        elif path.startswith(settings.UPLOAD_DIR):
            relative_path = path
        else:
            relative_path = path.lstrip("/")
        
        # 构建完整文件路径
        # relative_path 格式：uploads/DEV/2025/11/27/uuid.jpg 或 DEV/2025/11/27/uuid.jpg
        upload_base_dir = Path(__file__).parent.parent.parent / settings.UPLOAD_DIR
        if relative_path.startswith(settings.UPLOAD_DIR):
            # 如果包含 uploads 前缀，移除它
            relative_path = relative_path.replace(f"{settings.UPLOAD_DIR}/", "", 1)
        file_path = upload_base_dir / relative_path
        
        if file_path.exists() and file_path.is_file():
            return file_path
        return None
        
    except Exception:
        return None


def save_base64_image(base64_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    将 base64 字符串保存为图片文件
    
    Args:
        base64_str: base64 字符串（格式：data:image/jpeg;base64,xxx 或直接 base64 字符串）
    
    Returns:
        Tuple[Optional[str], Optional[str]]: (file_url, error_message)
        - file_url: 文件的 URL 路径，成功时返回，失败时返回 None
        - error_message: 错误消息，失败时返回，成功时返回 None
    """
    if not base64_str or not base64_str.strip():
        return None, "Base64 字符串为空"
    
    try:
        # 解析 base64 字符串
        # 支持格式：data:image/jpeg;base64,xxx 或直接 base64 字符串
        # 仅支持 jpg 和 png 格式
        base64_data = base64_str
        file_extension = ".jpg"  # 默认扩展名为 jpg
        
        if base64_str.startswith("data:image/"):
            # 解析 data URI
            header, base64_data = base64_str.split(",", 1)
            # 从 header 中提取文件类型，仅支持 jpg 和 png
            if "jpeg" in header.lower() or "jpg" in header.lower():
                file_extension = ".jpg"
            elif "png" in header.lower():
                file_extension = ".png"
            else:
                return None, f"不支持的图片格式：{header}，仅支持 jpg 和 png"
        
        # 验证文件扩展名（仅允许 jpg 和 png）
        if file_extension not in [".jpg", ".png"]:
            return None, "不支持的图片格式，仅支持 jpg 和 png"
        
        # 解码 base64
        try:
            image_data = base64.b64decode(base64_data)
        except Exception as e:
            return None, f"Base64 解码失败：{str(e)}"
        
        # 验证文件大小
        file_size = len(image_data)
        if file_size == 0:
            return None, "图片文件为空"
        
        if file_size > settings.MAX_UPLOAD_SIZE:
            max_size_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
            return None, f"图片文件过大，最大支持 {max_size_mb}MB"
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # 获取环境文件夹（APP_ENV 转大写，如 dev -> DEV）
        env_folder = settings.APP_ENV.upper()
        
        # 创建按环境、日期分组的目录结构
        # uploads/DEV/2025/11/28/uuid.jpg
        date_dir = datetime.now().strftime("%Y/%m/%d")
        upload_base_dir = Path(__file__).parent.parent.parent / settings.UPLOAD_DIR
        save_dir = upload_base_dir / env_folder / date_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存文件
        file_path = save_dir / unique_filename
        with open(file_path, "wb") as f:
            f.write(image_data)
        
        # 返回文件 URL（完整 URL，通过 API Gateway 访问）
        # /uploads/DEV/2025/11/28/uuid.jpg
        relative_path = f"/{settings.UPLOAD_DIR}/{env_folder}/{date_dir}/{unique_filename}"
        # 如果 BASE_URL 已配置，生成完整 URL；否则返回相对路径
        if settings.BASE_URL:
            file_url = f"{settings.BASE_URL.rstrip('/')}{relative_path}"
        else:
            file_url = relative_path
        
        return file_url, None
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error saving base64 image: {e}", exc_info=True)
        return None, f"保存图片失败：{str(e)}"

