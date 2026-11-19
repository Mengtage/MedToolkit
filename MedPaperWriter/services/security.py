"""
安全工具模块
提供文件上传安全验证、输入清理等功能
"""

import re
import os
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile


# 文件大小限制（10MB）
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 50 * 1024 * 1024

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'.docx', '.xlsx', '.csv', '.pdf', '.txt'}

# 文件魔数（文件签名）
FILE_SIGNATURES = {
    '.docx': b'PK\x03\x04',  # ZIP-based format
    '.xlsx': b'PK\x03\x04',  # ZIP-based format
    '.pdf': b'%PDF',
    '.txt': None,  # Text files have no specific signature
    '.csv': None,  # CSV files have no specific signature
}

# 危险的路径遍历字符
PATH_TRAVERSAL_PATTERNS = [
    r'\.\.',  # Parent directory
    r'/',      # Forward slash
    r'\\',     # Backslash
    r'\x00',   # Null byte
]


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，防止路径遍历攻击

    Args:
        filename: 原始文件名

    Returns:
        清理后的安全文件名
    """
    if not filename:
        return "unnamed_file"

    # 移除危险字符
    safe_filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

    # 限制文件名长度
    name, ext = os.path.splitext(safe_filename)
    max_name_length = 100
    if len(name) > max_name_length:
        name = name[:max_name_length]

    # 确保扩展名安全
    safe_ext = ext.lower() if ext else ''
    if safe_ext not in ALLOWED_EXTENSIONS:
        safe_ext = '.txt'

    return f"{name}{safe_ext}"


def get_file_extension(filename: str) -> str:
    """
    安全地获取文件扩展名

    Args:
        filename: 文件名

    Returns:
        文件扩展名（小写）
    """
    if not filename or '.' not in filename:
        return ''

    # 使用更安全的方法提取扩展名
    ext = os.path.splitext(filename)[1].lower()
    return ext


def validate_file_extension(filename: str) -> Tuple[bool, Optional[str]]:
    """
    验证文件扩展名是否安全

    Args:
        filename: 文件名

    Returns:
        (是否安全, 错误消息)
    """
    ext = get_file_extension(filename)

    if not ext:
        return False, "文件名缺少扩展名"

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"不允许的文件类型: {ext}"

    return True, None


def validate_file_size(size: int) -> Tuple[bool, Optional[str]]:
    """
    验证文件大小是否在限制内

    Args:
        size: 文件大小（字节）

    Returns:
        (是否安全, 错误消息)
    """
    if size <= 0:
        return False, "文件大小无效"

    if size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        return False, f"文件大小超过限制 ({max_mb:.0f}MB)"

    return True, None


async def validate_upload_file(
    file: UploadFile,
    max_size: int = MAX_FILE_SIZE
) -> Tuple[bool, Optional[str], bytes]:
    """
    验证上传文件的安全性，并返回读取的内容

    Args:
        file: 上传的文件对象
        max_size: 最大文件大小

    Returns:
        (是否安全, 错误消息, 文件内容)
    """
    # 检查文件名
    if not file.filename:
        return False, "文件名为空", b""

    # 验证扩展名
    is_valid, error = validate_file_extension(file.filename)
    if not is_valid:
        return False, error, b""

    # 读取文件内容
    content = await file.read()

    # 检查文件大小
    if len(content) > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"文件大小超过限制 ({max_mb:.0f}MB)", b""

    # 验证文件魔数
    ext = get_file_extension(file.filename)
    signature = FILE_SIGNATURES.get(ext)

    if signature and not content.startswith(signature):
        return False, f"文件内容与扩展名不匹配，可能是伪造的文件", b""

    return True, None, content


def sanitize_path(path: str) -> str:
    """
    清理路径，防止路径遍历

    Args:
        path: 原始路径

    Returns:
        清理后的安全路径
    """
    # 移除危险字符
    for pattern in PATH_TRAVERSAL_PATTERNS:
        path = re.sub(pattern, '', path)

    # 确保路径是相对路径
    path = path.lstrip('/\\')

    return path


def truncate_text(text: str, max_length: int = 100000) -> str:
    """
    截断过长的文本，防止内存耗尽

    Args:
        text: 原始文本
        max_length: 最大长度

    Returns:
        截断后的文本
    """
    if len(text) > max_length:
        return text[:max_length] + f"\n\n[内容已截断，原长度: {len(text)} 字符]"
    return text


def limit_list_items(items: list, max_items: int = 1000) -> list:
    """
    限制列表项数量

    Args:
        items: 原始列表
        max_items: 最大项数

    Returns:
        截断后的列表
    """
    if len(items) > max_items:
        return items[:max_items]
    return items
