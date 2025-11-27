"""
开发环境使用的控制台日志中间件
仅在配置启用时记录请求与响应，便于本地调试
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, AsyncIterator, cast, Optional, Tuple

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.core_config import settings
from app.utils.util_error_map import ERROR_CODE_TO_MESSAGE, get_error_code_from_message
from app.utils.util_request import get_request_id


logger = logging.getLogger("warehouse_server.dev_logging")
logger.setLevel(logging.INFO)

COLOR_RESET = "\033[0m"
COLOR_REQUEST = "\033[96m"  # Cyan
COLOR_RESPONSE = "\033[92m"  # Green
COLOR_ERROR = "\033[91m"  # Red

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)

logger.propagate = False


class DevLoggingMiddleware(BaseHTTPMiddleware):
    """在開發環境中輸出簡易請求/響應日誌"""

    async def dispatch(self, request: Request, call_next):
        # 統一處理並暫存 request_id（獲取順序：state > header > self gen）
        request_id = get_request_id(request)

        if not (settings.LOG_REQUEST_CONSOLE or settings.LOG_RESPONSE_CONSOLE):
            # 未啟用時直接透傳
            return await call_next(request)

        request_info = {}
        if settings.LOG_REQUEST_CONSOLE:
            request_info = await self._build_request_info(request, request_id)
            logger.info(
                "%s==== REQUEST START ====%s\n%s\n%s==== REQUEST END ====%s",
                COLOR_REQUEST,
                COLOR_RESET,
                self._format_block(request_info),
                COLOR_REQUEST,
                COLOR_RESET,
            )

        try:
            response = await call_next(request)
        except Exception as exc:
            if settings.LOG_RESPONSE_CONSOLE:
                error_code, error_message = self._resolve_exception_error(exc)
                logger.error(
                    "%s==== RESPONSE ERROR START ====%s\nrequest_id: %s\nurl: %s\nmethod: %s\ncode: %s\nmessage: %s\nerror: %s\n%s==== RESPONSE ERROR END ====%s",
                    COLOR_ERROR,
                    COLOR_RESET,
                    request_id,
                    request.url,
                    request.method,
                    error_code or "N/A",
                    error_message,
                    exc,
                    COLOR_ERROR,
                    COLOR_RESET,
                )
            raise

        if not settings.LOG_RESPONSE_CONSOLE:
            return response

        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is None:
            return response

        body_bytes = b""
        try:
            async for chunk in cast(AsyncIterator[bytes], body_iterator):
                body_bytes += chunk
        except Exception:
            return response

        payload = self._safe_decode(body_bytes)
        response_body_formatted = self._format_payload(payload)
        # 检查 internal_code 或 external_code（warehouse_server 使用 internal_code/external_code）
        business_code = self._extract_business_code(payload)
        if business_code is not None and business_code != 200:
            error_message = self._resolve_error_message(business_code, payload)
            logger.error(
                "%s==== RESPONSE ERROR START ====%s\npayload:\n%s\n%s==== RESPONSE ERROR END ====%s",
                COLOR_ERROR,
                COLOR_RESET,
                response_body_formatted,
                COLOR_ERROR,
                COLOR_RESET,
            )
        else:
            logger.info(
                "%s==== RESPONSE START ====%s\npayload:\n%s\n%s==== RESPONSE END ====%s",
                COLOR_RESPONSE,
                COLOR_RESET,
                response_body_formatted,
                COLOR_RESPONSE,
                COLOR_RESET,
            )

        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    async def _build_request_info(self, request: Request, request_id: str) -> Dict[str, Any]:
        headers = {
            k: ("***" if k.lower() in {"authorization", "cookie", "x-api-key"} else v)
            for k, v in request.headers.items()
        }
        body = await self._get_request_body(request)
        return {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "body": body,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def _get_request_body(self, request: Request) -> Any:
        try:
            body_bytes = await request.body()
            if not body_bytes:
                return {}

            # 重新注入 body，避免後續 handler 無法再次讀取
            body_consumed = False

            async def receive():
                nonlocal body_consumed
                if not body_consumed:
                    body_consumed = True
                    return {"type": "http.request", "body": body_bytes, "more_body": False}
                return {"type": "http.request", "body": b"", "more_body": False}

            request._receive = receive

            try:
                payload = json.loads(body_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                payload = body_bytes.decode("utf-8", errors="ignore")[:500]

            if isinstance(payload, dict):
                sensitive_fields = {"password", "new_password", "old_password"}
                return {
                    k: ("***" if isinstance(v, str) and k.lower() in sensitive_fields else v)
                    for k, v in payload.items()
                }
            return payload
        except Exception as exc:
            return {"error": f"Failed to read body: {str(exc)}"}

    def _safe_decode(self, body_bytes: bytes) -> Any:
        if not body_bytes:
            return ""
        try:
            return json.loads(body_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return body_bytes.decode("utf-8", errors="ignore")[:500]

    @staticmethod
    def _format_block(payload: Dict[str, Any]) -> str:
        lines = []
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                formatted = json.dumps(value, ensure_ascii=False, indent=2)
                lines.append(f"{key}: {formatted}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _format_payload(payload: Any) -> str:
        if isinstance(payload, (dict, list)):
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return str(payload)

    @staticmethod
    def _extract_business_code(payload: Any) -> Optional[int]:
        """提取业务错误码（优先使用 internal_code，如果没有则使用 external_code）"""
        if isinstance(payload, dict):
            # 优先使用 internal_code（warehouse_server 使用 internal_code/external_code）
            internal_code = payload.get("internal_code")
            if isinstance(internal_code, int):
                return internal_code
            # 如果没有 internal_code，尝试使用 external_code
            external_code = payload.get("external_code")
            if isinstance(external_code, int):
                return external_code
            # 兼容旧格式（使用 code）
            code = payload.get("code")
            if isinstance(code, int):
                return code
        return None

    @staticmethod
    def _resolve_error_message(code: int, payload: Any) -> str:
        message = None
        if isinstance(payload, dict):
            msg_value = payload.get("message")
            if isinstance(msg_value, str):
                message = msg_value
        return message or ERROR_CODE_TO_MESSAGE.get(code, "Unknown error")

    @staticmethod
    def _resolve_exception_error(exc: Exception) -> Tuple[Optional[int], str]:
        code: Optional[int] = None
        message: str = str(exc)

        if isinstance(exc, HTTPException):
            detail = exc.detail
            if isinstance(detail, dict):
                maybe_code = detail.get("code")
                if isinstance(maybe_code, int):
                    code = maybe_code
                detail_message = detail.get("message")
                if isinstance(detail_message, str):
                    message = detail_message
            elif isinstance(detail, str):
                code = get_error_code_from_message(detail)
                message = detail

        mapped_message = ERROR_CODE_TO_MESSAGE.get(code, message) if code else message
        return code, mapped_message

