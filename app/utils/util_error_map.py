"""
Warehouse 服务错误码和错误消息定义

此文件由 script/generate_error_map.py 自动生成
如需修改错误码或消息，请编辑 resource/feature_code_map.json 后运行生成脚本

生成命令:
    python3 script/generate_error_map.py
"""

ERROR_CODE_TO_MESSAGE = {
    400: "Internal server error",
    401: "Warehouse service failed",
    402: "Request parameters invalid",
    403: "Request path invalid",
    404: "Unauthorized",
    410: "Internal server error",
    411: "Cabinet service failed",
    412: "Request parameters invalid",
    413: "Request path invalid",
    414: "Unauthorized",
    415: "Cabinet not found",
    416: "Cabinet name already exists",
    420: "Internal server error",
    421: "Item service failed",
    422: "Request parameters invalid",
    423: "Request path invalid",
    424: "Unauthorized",
    425: "Item not found",
    426: "Item name already exists",
    427: "Insufficient stock",
    428: "Cabinet not found",
    430: "Internal server error",
    431: "Category service failed",
    432: "Request parameters invalid",
    433: "Request path invalid",
    434: "Unauthorized",
    435: "Category not found",
    436: "Category name already exists",
    437: "Category level exceeds maximum",
    438: "Cannot delete category with items",
    440: "Internal server error",
    441: "Log service failed",
    442: "Request parameters invalid",
    443: "Request path invalid",
    444: "Unauthorized",
    445: "Log not found",
}


ERROR_NAME_TO_CODE = {
    "INTERNAL_SERVER_ERROR_40": 400,
    "WAREHOUSE_SERVICE_FAILED_40": 401,
    "REQUEST_PARAMETERS_INVALID_40": 402,
    "REQUEST_PATH_INVALID_40": 403,
    "UNAUTHORIZED_40": 404,
    "INTERNAL_SERVER_ERROR_41": 410,
    "CABINET_SERVICE_FAILED_41": 411,
    "REQUEST_PARAMETERS_INVALID_41": 412,
    "REQUEST_PATH_INVALID_41": 413,
    "UNAUTHORIZED_41": 414,
    "CABINET_NOT_FOUND_41": 415,
    "CABINET_NAME_ALREADY_EXISTS_41": 416,
    "INTERNAL_SERVER_ERROR_42": 420,
    "ITEM_SERVICE_FAILED_42": 421,
    "REQUEST_PARAMETERS_INVALID_42": 422,
    "REQUEST_PATH_INVALID_42": 423,
    "UNAUTHORIZED_42": 424,
    "ITEM_NOT_FOUND_42": 425,
    "ITEM_NAME_ALREADY_EXISTS_42": 426,
    "INSUFFICIENT_STOCK_42": 427,
    "CABINET_NOT_FOUND_42": 428,
    "INTERNAL_SERVER_ERROR_43": 430,
    "CATEGORY_SERVICE_FAILED_43": 431,
    "REQUEST_PARAMETERS_INVALID_43": 432,
    "REQUEST_PATH_INVALID_43": 433,
    "UNAUTHORIZED_43": 434,
    "CATEGORY_NOT_FOUND_43": 435,
    "CATEGORY_NAME_ALREADY_EXISTS_43": 436,
    "CATEGORY_LEVEL_EXCEEDS_MAXIMUM_43": 437,
    "CANNOT_DELETE_CATEGORY_WITH_ITEMS_43": 438,
    "INTERNAL_SERVER_ERROR_44": 440,
    "LOG_SERVICE_FAILED_44": 441,
    "REQUEST_PARAMETERS_INVALID_44": 442,
    "REQUEST_PATH_INVALID_44": 443,
    "UNAUTHORIZED_44": 444,
    "LOG_NOT_FOUND_44": 445,
}


class _ServerErrorCode:
    def __getattr__(self, name: str) -> int:
        if name in ERROR_NAME_TO_CODE:
            return ERROR_NAME_TO_CODE[name]
        raise AttributeError(f"{self.__class__.__name__} has no attribute '{name}'")


class _ServerErrorMessage:
    def __getattr__(self, name: str) -> str:
        if name in ERROR_NAME_TO_CODE:
            return "Warehouse Service Failed"
        raise AttributeError(f"{self.__class__.__name__} has no attribute '{name}'")


ServerErrorCode = _ServerErrorCode()
ServerErrorMessage = _ServerErrorMessage()


def get_error_code_from_message(message: str):
    for code, msg in ERROR_CODE_TO_MESSAGE.items():
        if msg == message:
            return code
    return None
