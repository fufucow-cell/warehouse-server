#!/usr/bin/env python3
"""
从 feature_code_map.json 文件自动生成 util_error_map.py 文件

使用方法:
    python3 script/generate_error_map.py
    或
    ./script/generate_error_map.py
"""

import json
import sys
from pathlib import Path


def message_to_name(message: str) -> str:
    """将消息转换为枚举名称（UPPER_SNAKE_CASE）"""
    # 移除特殊字符，只保留字母数字和空格
    name = ''.join(c if c.isalnum() or c == ' ' else ' ' for c in message)
    # 将多个空格替换为单个空格
    name = ' '.join(name.split())
    # 转换为大写并用下划线替换空格
    name = name.upper().replace(' ', '_')
    # 移除末尾的下划线
    name = name.rstrip('_')
    return name


def escape_message(message: str) -> str:
    """转义消息中的引号"""
    return message.replace('"', '\\"')


def get_script_dir():
    """获取脚本所在目录"""
    return Path(__file__).parent.absolute()


def get_project_root():
    """获取项目根目录"""
    return get_script_dir().parent


def extract_errors_from_feature_map(feature_data: dict) -> list:
    """从 feature_code_map.json 提取所有错误信息"""
    errors = []
    for router in feature_data.get("routers", []):
        router_code = router.get("router_code", "")
        for error in router.get("errors", []):
            errors.append({
                "code": int(error["error_code"]),
                "message": error["error_message"],
                "router_code": router_code
            })
    return errors


def generate_error_maps(error_list: list) -> tuple[str, str]:
    """生成错误映射字典"""
    print("[DEBUG] 开始生成错误映射字典...", file=sys.stderr)
    
    # 按错误码排序
    error_list = sorted(error_list, key=lambda x: x['code'])
    
    # 生成错误码 -> 错误消息映射
    error_code_to_message = []
    error_code_to_message.append("ERROR_CODE_TO_MESSAGE = {")
    for item in error_list:
        code = item['code']
        message = item['message']
        escaped_message = escape_message(message)
        error_code_to_message.append(f"    {code}: \"{escaped_message}\",")
    error_code_to_message.append("}")
    error_code_to_message.append("")
    
    # 生成名称 -> 错误码映射
    error_name_to_code = []
    error_name_to_code.append("ERROR_NAME_TO_CODE = {")
    
    for item in error_list:
        code = item['code']
        message = item['message']
        router_code = item.get('router_code', '')
        name = message_to_name(message)
        
        # 所有名称后面都加上 router_code
        if router_code:
            name = f"{name}_{router_code}"
        
        error_name_to_code.append(f"    \"{name}\": {code},")
    error_name_to_code.append("}")
    
    print("[DEBUG] 错误映射字典生成完成", file=sys.stderr)
    return '\n'.join(error_code_to_message), '\n'.join(error_name_to_code)


def generate_error_map_py(error_list: list) -> str:
    """生成完整的 error_map.py 文件"""
    print("[DEBUG] 开始生成 Python 代码...", file=sys.stderr)
    
    error_code_to_message, error_name_to_code = generate_error_maps(error_list)
    
    python_code = f'''"""
Warehouse 服务错误码和错误消息定义

此文件由 script/generate_error_map.py 自动生成
如需修改错误码或消息，请编辑 resource/feature_code_map.json 后运行生成脚本

生成命令:
    python3 script/generate_error_map.py
"""

{error_code_to_message}

{error_name_to_code}


class _ServerErrorCode:
    def __getattr__(self, name: str) -> int:
        if name in ERROR_NAME_TO_CODE:
            return ERROR_NAME_TO_CODE[name]
        raise AttributeError(f"{{self.__class__.__name__}} has no attribute '{{name}}'")


class _ServerErrorMessage:
    def __getattr__(self, name: str) -> str:
        if name in ERROR_NAME_TO_CODE:
            return "Warehouse Service Failed"
        raise AttributeError(f"{{self.__class__.__name__}} has no attribute '{{name}}'")


ServerErrorCode = _ServerErrorCode()
ServerErrorMessage = _ServerErrorMessage()


def get_error_code_from_message(message: str):
    for code, msg in ERROR_CODE_TO_MESSAGE.items():
        if msg == message:
            return code
    return None
'''
    
    print("[DEBUG] Python 代码生成完成", file=sys.stderr)
    return python_code


def main():
    """主函数"""
    print("[DEBUG] 脚本开始执行...", file=sys.stderr)
    
    # 获取路径
    script_dir = get_script_dir()
    project_root = get_project_root()
    json_path = project_root / "resource" / "feature_code_map.json"
    output_path = project_root / "app" / "utils" / "util_error_map.py"
    
    print(f"[DEBUG] SCRIPT_DIR={script_dir}", file=sys.stderr)
    print(f"[DEBUG] PROJECT_ROOT={project_root}", file=sys.stderr)
    print(f"[DEBUG] JSON_PATH={json_path}", file=sys.stderr)
    print(f"[DEBUG] OUTPUT_PATH={output_path}", file=sys.stderr)
    
    # 检查 JSON 文件是否存在
    print("[DEBUG] 检查 JSON 文件...", file=sys.stderr)
    if not json_path.exists():
        print(f"错误: 找不到 JSON 文件: {json_path}", file=sys.stderr)
        sys.exit(1)
    print("[DEBUG] JSON 文件存在", file=sys.stderr)
    
    # 读取 JSON 文件
    print("[DEBUG] 读取 JSON 文件...", file=sys.stderr)
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            feature_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 文件格式错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取 JSON 文件失败: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 从 feature_code_map.json 提取所有错误
    error_list = extract_errors_from_feature_map(feature_data)
    print(f"[DEBUG] JSON 文件读取成功，共 {len(error_list)} 个错误", file=sys.stderr)
    
    # 创建输出目录
    print("[DEBUG] 创建输出目录...", file=sys.stderr)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print("[DEBUG] 输出目录已创建", file=sys.stderr)
    
    # 生成 Python 代码
    print("[DEBUG] 进入主函数...", file=sys.stderr)
    print("[DEBUG] 调用 generate_error_map_py...", file=sys.stderr)
    python_code = generate_error_map_py(error_list)
    
    # 写入文件
    print("[DEBUG] 开始写入文件...", file=sys.stderr)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(python_code)
    except Exception as e:
        print(f"错误: 写入文件失败: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[DEBUG] 文件写入完成: {output_path}", file=sys.stderr)
    print(f"✓ 成功生成: {output_path}")
    print(f"  从 JSON 文件: {json_path}")


if __name__ == "__main__":
    main()

