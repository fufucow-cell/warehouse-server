import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, List
from uuid import UUID
from fastapi import Request, status
from app.core.core_config import settings
from app.utils.util_request import get_request_id, get_user_id


_SENSITIVE_FIELDS: set[str] = {"password", "access_token", "refresh_token"}

class JSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def log_info(
    request_data: Dict[str, Any],
    response_data: Dict[str, Any],
    request: Optional[Request] = None
) -> None:
    if request is None:
        return
    
    log_request(request_data, request)
    log_response(response_data, request)

# 記錄請求日誌
def log_request(
    request_data: Dict[str, Any],
    request: Optional[Request] = None
) -> None:
    if request is None:
        return
    
    try:
        if settings.ENABLE_LOG:
            request_info: Dict[str, Any] = {}
            tz_utc_8 = timezone(timedelta(hours=8))
            request_info["timestamp"] = datetime.now(tz_utc_8).strftime("%Y-%m-%d %H:%M:%S")
            request_info["method"] = request.method
            request_info["path"] = request.url.path
            request_id_uuid = get_request_id(request)
            user_id_uuid = get_user_id(request)
            request_info["request_id"] = str(request_id_uuid) if request_id_uuid else None
            request_info["user_id"] = str(user_id_uuid) if user_id_uuid else None
            
            # 添加 headers 資訊
            headers_dict = {}
            
            for key, value in request.headers.items():
                headers_dict[key.lower()] = value
            
            request_info["headers"] = headers_dict
            
            # 添加 query_params 資訊
            request_info["query_params"] = dict(request.query_params)
              
            # 添加 body 資訊（已解析的数据）
            if request_data:
                request_info["body"] = request_data
            
            # 过滤敏感信息
            _filter_sensitive_data(request_info)
            
            _write_log(request_info, "request_normal")
    except Exception:
        pass

# 記錄響應日誌
def log_response(
    response_data: Dict[str, Any],
    request: Optional[Request] = None
) -> None:
    if not settings.ENABLE_LOG:
        return

    if not response_data or not isinstance(response_data, dict):
        return

    try:
        response_info: Dict[str, Any] = {}
        tz_utc_8 = timezone(timedelta(hours=8))
        response_info["timestamp"] = datetime.now(tz_utc_8).strftime("%Y-%m-%d %H:%M:%S")
        
        if response_data:
            response_info["body"] = response_data
        
        is_success = (
            response_data.get("internal_code") == status.HTTP_200_OK and
            response_data.get("external_code") == status.HTTP_200_OK
        )
        
        _filter_sensitive_data(response_data)
        log_subdir = "response_normal" if is_success else "response_error"
        _write_log(response_data, log_subdir)
    except Exception:
        pass

# 過濾敏感資料
def _filter_sensitive_data(data: Dict[str, Any]) -> None:
    for key in data.keys():
        if key in _SENSITIVE_FIELDS:
            data[key] = "*"
        elif isinstance(data[key], dict):
            _filter_sensitive_data(data[key])
        elif isinstance(data[key], list):
            for item in data[key]:
                if isinstance(item, dict):
                    _filter_sensitive_data(item)

# 寫入日誌
def _write_log(log_data: Dict[str, Any], log_subdir: str) -> None:
    try:
        project_root = Path(__file__).parent.parent.parent
        log_dir: Path = project_root / "log" / settings.APP_ENV / log_subdir
        log_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime("%Y-%m-%d")
        log_file: Path = log_dir / f"log_{today}.txt"
        
        log_content: str = json.dumps(log_data, ensure_ascii=False, indent=2, cls=JSONEncoder)
        
        with open(log_file, "a", encoding="utf-8") as file:
            file.write(log_content + "\n\n")
            
    except Exception:
        pass

# 記錄 OpenAI API 響應日誌
def log_openai_result(
    user_id: Optional[str],
    request_id: Optional[str],
    openai_response: Dict[str, Any]
) -> None:
    if not settings.ENABLE_LOG:
        return
    
    try:
        log_data = {
            "user_id": user_id,
            "request_id": request_id,
            "data": openai_response
        }
        
        project_root = Path(__file__).parent.parent.parent
        log_dir: Path = project_root / "log" / settings.APP_ENV / "open_ai_result"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime("%Y-%m-%d")
        log_file: Path = log_dir / f"log_{today}.txt"
        
        log_content: str = json.dumps(log_data, ensure_ascii=False, indent=2, cls=JSONEncoder)
        
        with open(log_file, "a", encoding="utf-8") as file:
            file.write(log_content + "\n\n")
            
    except Exception:
        pass